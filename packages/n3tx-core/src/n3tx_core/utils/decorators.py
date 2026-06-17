# app/utils/decorators.py
import inspect
import time
import json
import logging
from dataclasses import dataclass
from functools import wraps
from typing import Callable

from n3tx_core import config

logger = logging.getLogger('n3tx.debug')


@dataclass(frozen=True)
class ExposedMethodInfo:
    """Normalized metadata for a model method marked with @expose_route.

    Python descriptor lookup hides whether a method was declared with
    ``@staticmethod`` or ``@classmethod``: ``getattr(cls, name)`` returns the
    bound/callable object, not the raw descriptor. Schema generation, route
    registration, and actor dispatch need the raw declaration shape so they can
    decide whether an entity id is required.
    """
    name: str
    raw: object
    func: Callable
    bound: Callable
    endpoint: dict
    scope: str
    requires_instance: bool


def exposed_method_info(cls, name: str) -> ExposedMethodInfo | None:
    """Return descriptor-aware @expose_route metadata for ``cls.name``.

    Scopes are intentionally behavioral:
    - ``instancemethod`` requires an entity instance/id
    - ``classmethod`` and ``staticmethod`` are collection/class capabilities
    - ``actormethod`` is a service-style actor capability with no self/cls
    """
    try:
        raw = inspect.getattr_static(cls, name)
        bound = getattr(cls, name)
    except AttributeError:
        return None

    if isinstance(raw, classmethod):
        func = raw.__func__
        scope = 'classmethod'
        requires_instance = False
    elif isinstance(raw, staticmethod):
        func = raw.__func__
        scope = 'staticmethod'
        requires_instance = False
    else:
        func = raw
        if not callable(func):
            return None
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            return None
        if 'self' in sig.parameters:
            scope = 'instancemethod'
            requires_instance = True
        elif 'cls' in sig.parameters:
            scope = 'classmethod'
            requires_instance = False
        else:
            scope = 'actormethod'
            requires_instance = False

    endpoint = getattr(func, '__endpoint__', None) or getattr(bound, '__endpoint__', None)
    if endpoint is None or not callable(bound):
        return None

    return ExposedMethodInfo(
        name=name,
        raw=raw,
        func=func,
        bound=bound,
        endpoint=endpoint,
        scope=scope,
        requires_instance=requires_instance,
    )


def expose_route(route, methods=["POST"], access=None, stream=False, events=None):
    """
    Decorator to mark a method as an endpoint to be exposed via the API.
    Args:
        route (str): The route to be used, relative to the base model route.
        methods (list): The HTTP methods allowed for this route.
        access (AccessRule, optional): Authorization rule for this endpoint.
            If None, falls back to model's __access__ dict or AUTHENTICATED default.
        stream (bool): If True, marks this method as a streaming endpoint.
            Streaming methods must be async generators (use yield, not return).
        events (dict, optional): Map of event name to ProtoModel subclass for
            streaming methods. Declares the schema of each stream event type.
            Example: events={'text': TextChunk, 'done': DoneChunk}
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not config.DEBUG:
                return func(*args, **kwargs)

            result = func(*args, **kwargs)

            # Async generators must pass through — debug envelope would break streaming
            if inspect.isasyncgen(result):
                return result

            # Async coroutines must pass through — caller needs to await them
            if inspect.iscoroutine(result):
                return result

            start = time.monotonic()
            elapsed = round((time.monotonic() - start) * 1000, 2)

            # Extract instance_id from self (first arg for instance methods)
            instance_id = None
            if args and hasattr(args[0], 'id'):
                instance_id = getattr(args[0], 'id', None)

            # Extract model name from self.__class__ or cls
            model_name = None
            if args:
                obj = args[0]
                model_name = obj.__name__ if isinstance(obj, type) else type(obj).__name__

            # Normalize result so envelope is uniform (serializable)
            parsed_result = result
            if hasattr(result, 'model_dump'):
                parsed_result = result.model_dump()
            elif isinstance(result, str):
                try:
                    parsed_result = json.loads(result)
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                'data': parsed_result,
                '_debug': {
                    'method': func.__name__,
                    'model': model_name,
                    'instance_id': instance_id,
                    'duration_ms': elapsed,
                }
            }

        wrapper.__endpoint__ = {
            'route': route,
            'methods': methods,
            'access': access,
            'stream': stream,
            'events': events,
        }
        # Preserve __globals__ so get_type_hints() can resolve forward refs
        # (e.g., 'Comment' in the model's module). functools.wraps doesn't copy this.
        wrapper.__globals__.update(func.__globals__)
        return wrapper
    return decorator
