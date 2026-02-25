import logging
import traceback
from fastapi import HTTPException

logger = logging.getLogger('pybend.utils')


class MethodError(Exception):
    """Raised by custom model methods to signal an HTTP error response.

    Custom ``@expose_route`` methods live in model code that should not
    import FastAPI directly.  Raising ``MethodError`` instead of returning
    a JSON error string lets the route handler (``make_custom_post``)
    translate the error into a proper ``HTTPException`` with the correct
    status code.

    Usage in a model method::

        from pybend.core.utils.erroring import MethodError

        @expose_route('/like', methods=['POST'])
        def like(self, user=None):
            if not user:
                raise MethodError("authentication required", 401)
    """

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_traceback_info(e: Exception):
    """
    Extracts the last three frames of the traceback from an exception and formats them
    properly to be used in the response.
    """
    tb = traceback.extract_tb(e.__traceback__)
    last_frames = tb[-3:] if tb else []

    trace_info = [
        {
            "file": frame.filename,
            "line": frame.lineno,
            "function": frame.name,
            "code": frame.line
        }
        for frame in last_frames
    ]
    trace_info[-1]['error'] = str(e)

    return trace_info
