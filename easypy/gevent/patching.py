
try:
    import gevent
    from gevent.monkey import is_module_patched
except ImportError:
    def is_module_patched(*_, **__):
        return False


from logging import getLogger
import os
import threading
import time
import sys


from easypy.humanize import format_thread_stack
from easypy.gevent import non_patched_threadpool
from easypy.gevent.non_patched_threadpool import NonPatchedThreadPool

_logger = getLogger()


main_thread_ident_before_patching = threading.main_thread().ident
_greenlet_trace_func = None
HUB = None

WARN_BLOCK_TIME_SEC = 1
# FAIL_BLOCK_TIME_SEC = 60


def apply_gevent_patch(hogging_detection=False, non_patched_threadpool_size=1):
    _logger.info('applying gevent patch')

    disable_gevent = os.environ.get('bamboo_no_gevent')
    if disable_gevent:
        _logger.info('YELLOW<<gevent was not applied. bamboo_no_gevent=%s>>', disable_gevent)
        return

    # non_patched_threadpool_size is 1 by default so it will be possible to run watch_threads concurrently
    if hogging_detection:
        non_patched_threadpool_size += 1

    if non_patched_threadpool_size:
        non_patched_threadpool.non_patched_threadpool = NonPatchedThreadPool(non_patched_threadpool_size)

    patch_module_locks()

    import gevent
    import gevent.monkey

    gevent.monkey.patch_all(Event=True, sys=True)

    unpatch_logging_handlers_lock()

    global HUB
    HUB = gevent.get_hub()

    if hogging_detection:
        import greenlet
        greenlet.settrace(lambda e, a: _greenlet_trace_func(e, a) if _greenlet_trace_func else None)
        non_patched_threadpool.non_patched_threadpool.send_job(detect_hogging, 'detect-hogging')


def patch_module_locks():
    # gevent will not patch existing locks (including ModuleLocks) when it's not single threaded
    # our solution is to monley patch the release method for ModuleLocks objects
    # we assume that patching is done early enough so no other locks are present

    import importlib
    _old_relase = importlib._bootstrap._ModuleLock.release

    def _release(*args, **kw):
        lock = args[0]
        if lock.owner == main_thread_ident_before_patching:
            lock.owner = threading.main_thread().ident
        _old_relase(*args, **kw)

    importlib._bootstrap._ModuleLock.release = _release


def unpatch_logging_handlers_lock():
    # we dont want to use logger locks since those are used by both real thread and gevent greenlets
    # switching from one to the other will cause gevent hub to throw an exception
    import logging

    RLock = gevent.monkey.saved['threading']['_CRLock']

    for handler in logging._handlers.values():
        if handler.lock:
            handler.lock = RLock()

    def create_unpatched_lock_for_handler(handler):
        handler.lock = RLock()

    # patch future handlers
    logging.Handler.createLock = create_unpatched_lock_for_handler


def detect_hogging():
    did_switch = True

    current_running_greenlet = HUB

    def mark_switch(event, args):
        nonlocal did_switch
        nonlocal current_running_greenlet
        if event != 'switch':
            return
        did_switch = True
        current_running_greenlet = args[1]  # args = [origin_greenlet , target_greenlet

    global _greenlet_trace_func
    _greenlet_trace_func = mark_switch

    _current_blocker_time = 0
    _last_warning_time = 0

    while True:
        gevent.monkey.saved['time']['sleep'](WARN_BLOCK_TIME_SEC)

        if not did_switch and current_running_greenlet != HUB:  # it's ok for the hub to block if all greenlet wait on async io
            _current_blocker_time += WARN_BLOCK_TIME_SEC
            if _current_blocker_time < _last_warning_time * 2:
                continue  # dont dump too much warnings - decay exponentialy until exploding after FAIL_BLOCK_TIME_SEC
            for thread in threading.enumerate():
                if getattr(thread, '_greenlet', None) == current_running_greenlet:
                    _logger.info('RED<<greentlet hogger detected (%s seconds):>>', _current_blocker_time)
                    _logger.debug('thread stuck: %s', thread)
                    break
            else:
                _logger.info('RED<<greentlet hogger detected (%s seconds):>>', _current_blocker_time)
                _logger.deubg('greenlet stuck (no corresponding thread found): %s', current_running_greenlet)
            _logger.info(format_thread_stack(sys._current_frames()[main_thread_ident_before_patching]))
            _last_warning_time = _current_blocker_time
            continue

        _current_blocker_time = 0
        _last_warning_time = 0
        did_switch = False

