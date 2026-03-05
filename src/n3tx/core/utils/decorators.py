# app/utils/decorators.py
import time
import json
import logging
from functools import wraps

from n3tx.core import config

logger = logging.getLogger('n3tx.debug')


def expose_route(route, methods=["POST"], access=None, stream=False):
    """
    Decorator to mark a method as an endpoint to be exposed via the API.
    Args:
        route (str): The route to be used, relative to the base model route.
        methods (list): The HTTP methods allowed for this route.
        access (AccessRule, optional): Authorization rule for this endpoint.
            If None, falls back to model's __access__ dict or AUTHENTICATED default.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not config.DEBUG:
                return func(*args, **kwargs)

            start = time.monotonic()
            result = func(*args, **kwargs)
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

            # Parse JSON string results so envelope is uniform
            parsed_result = result
            if isinstance(result, str):
                try:
                    parsed_result = json.loads(result)
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                'result': parsed_result,
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
        }
        # Preserve __globals__ so get_type_hints() can resolve forward refs
        # (e.g., 'Comment' in the model's module). functools.wraps doesn't copy this.
        wrapper.__globals__.update(func.__globals__)
        return wrapper
    return decorator
