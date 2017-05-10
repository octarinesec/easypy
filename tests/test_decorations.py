import pytest

from functools import wraps

from easypy.decorations import deprecated_arguments, parametrizeable_decorator, late_decorator


def test_deprecated_arguments():
    @deprecated_arguments(foo='bar')
    def func(bar):
        return 'bar is %s' % (bar,)

    assert func(1) == func(foo=1) == func(bar=1) == 'bar is 1'

    with pytest.raises(TypeError):
        func(foo=1, bar=2)

    with pytest.raises(TypeError):
        func(1, foo=2)


def test_late_decorator_lambda():
    @parametrizeable_decorator
    def add_to_result(func, num):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs) + num

        wrapper.__name__ = '%s + %s' % (func.__name__, num)

        return wrapper

    class Foo:
        def __init__(self, num):
            self.num = num

        @late_decorator(lambda self: add_to_result(num=self.num))
        def foo(self):
            """foo doc"""
            return 1

    foo = Foo(10)
    assert foo.foo() == 11

    assert Foo.foo.__name__ == 'foo'
    assert foo.foo.__name__ == 'foo + 10'

    assert Foo.foo.__doc__ == foo.foo.__doc__ == 'foo doc'


def test_late_decorator_attribute():
    class Foo:
        def add_to_result(self, func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs) + self.num

            wrapper.__name__ = '%s + %s' % (func.__name__, self.num)

            return wrapper

        @late_decorator('add_to_result')
        def foo(self):
            """foo doc"""
            return 1

    foo = Foo()

    with pytest.raises(AttributeError):
        # We did not set foo.num yet, so the decorator will fail trying to set the name
        foo.foo

    foo.num = 10
    assert foo.foo() == 11
    assert foo.foo.__name__ == 'foo + 10'
    assert Foo.foo.__doc__ == foo.foo.__doc__ == 'foo doc'

    foo.num = 20
    assert foo.foo() == 21
    assert foo.foo.__name__ == 'foo + 20'
