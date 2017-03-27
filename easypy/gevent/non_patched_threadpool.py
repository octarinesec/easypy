from logging import getLogger
from queue import Queue
import threading


_logger = getLogger()
non_patched_threadpool = None


class NonPatchedThreadPool:
    def __init__(self, pool_size):
        self.pool_size = pool_size
        self.jobs_queue = Queue()
        self._initialize()

    def send_job(self, job, name=None):
        self.jobs_queue.put((job, name))

    def _initialize(self):

        def work():
            _logger.debug('starting non patched threadpool worker')
            while True:
                job, name = self.jobs_queue.get()
                if name:
                    _logger.debug('starting job on real thread: %s', name)
                else:
                    _logger.debug('starting job on real thread')
                job()
                _logger.debug('ready for the next job')

        threading.Thread.uuid = 'WORKER'  # adding dummy thread uuid so it's possible to watch these threads using watch_threads
        for i in range(self.pool_size):
            t = threading.Thread(target=work, name='real-thread-worker-%s' % i, daemon=True)
            t.start()

