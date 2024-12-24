# app/utils/decorators.py

def expose_route(route, methods=["POST"]):
    """
    Decorator to mark a method as an endpoint to be exposed via Flask.
    Args:
        route (str): The route to be used, relative to the base model route.
        methods (list): The HTTP methods allowed for this route.
    """
    def decorator(func):
        func.__endpoint__ = {
            'route': route,
            'methods': methods
        }
        return func
    return decorator
