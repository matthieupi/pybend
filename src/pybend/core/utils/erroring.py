import traceback
from fastapi import HTTPException

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
