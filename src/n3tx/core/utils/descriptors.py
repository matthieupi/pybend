"""Descriptors for unified class/instance dispatch.

fullmethod  — a method where the first param receives cls or self
fullproperty — a property that resolves class or instance state

These work on any class, not just Actors.
"""

from types import MethodType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TypeVar
    _F = TypeVar('_F')
    def fullmethod(fn: _F) -> _F: ...  # noqa: E704
    def fullproperty(fn: _F) -> _F: ...  # noqa: E704
else:
    class fullmethod:
        """A method that works on both classes and instances.

        The first parameter receives the class (when called as cls.method())
        or the instance (when called as self.method()). One function, one
        implementation — no dual paths.

            @fullmethod
            def ctx(target):  # target is cls or self
                ...

        Python mechanics:
            Product.ctx  → __get__(None, Product) → MethodType(fn, Product)
            product.ctx  → __get__(product, type) → MethodType(fn, product)
        """

        def __init__(self, fn):
            self.fn = fn
            self.__doc__ = fn.__doc__
            self.__name__ = fn.__name__

        def __set_name__(self, owner, name):
            self.__name__ = name

        def __get__(self, obj, cls=None):
            target = obj if obj is not None else cls
            return MethodType(self.fn, target)


    class fullproperty:
        """A property that works on both classes and instances.

        The function receives the class or instance and returns a value.
        Unlike fullmethod, this returns the value directly — not a callable.

            @fullproperty
            def children(target):
                if isinstance(target, type):
                    return target.__children__
                return target._children

        Python mechanics:
            Product.children  → __get__(None, Product) → fn(Product) → dict
            product.children  → __get__(product, type)  → fn(product) → dict
        """

        def __init__(self, fn):
            self.fn = fn
            self.__doc__ = fn.__doc__

        def __set_name__(self, owner, name):
            self.__name__ = name

        def __get__(self, obj, cls=None):
            target = obj if obj is not None else cls
            return self.fn(target)
