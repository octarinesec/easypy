from collections import defaultdict
from functools import wraps
from inspect import isgeneratorfunction
from contextlib import ExitStack, contextmanager, _GeneratorContextManager


class KeyedStack(ExitStack):
    def __init__(self, context_factory):
        self.context_factory = context_factory
        self.contexts_dict = defaultdict(list)
        super().__init__()

    def enter_context(self, *key):
        cm = self.context_factory(*key)
        self.contexts_dict[key].append(cm)
        super().enter_context(cm)

    def exit_context(self, *key):
        self.contexts_dict[key].pop(-1).__exit__(None, None, None)


def _better_GeneratorContextManager__call__(self, func):
    if isgeneratorfunction(func):
        def inner(*args, **kwds):
            with self._recreate_cm():
                yield from func(*args, **kwds)
    elif is_contextmanager(func):
        @contextmanager
        def inner(*args, **kwds):
            with self._recreate_cm():
                with func(*args, **kwds) as ret:
                    yield ret
    else:
        def inner(*args, **kwds):
            with self._recreate_cm():
                return func(*args, **kwds)
    return wraps(func)(inner)


_GeneratorContextManager.__call__ = _better_GeneratorContextManager__call__


# we use this to identify functions decorated by 'contextmanager'
_ctxm_code_sample = contextmanager(None).__code__


def is_contextmanager(func):
    return getattr(func, "__code__", None) is _ctxm_code_sample
