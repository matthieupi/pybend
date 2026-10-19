"""Logging configuration for N3TX applications.

Sets up the root logger to use Uvicorn's colourized, aligned formatter so that
application and framework log output is visually consistent with Uvicorn's own
access/error logs::

    INFO:     n3tx.storage: Database opened
    WARNING:  veille.scheduler: Run queue is full
    ERROR:    n3tx.agents: Tool discovery failed
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with Uvicorn's colourized formatter.

    Should be called once at application startup (``N3TXApp.__init__`` does
    this automatically).  Calling it again is safe — ``force=True`` replaces
    existing handlers.

    Args:
        level: Root log level.  Defaults to ``logging.INFO``.
    """
    try:
        from uvicorn.logging import DefaultFormatter
        fmt = DefaultFormatter('%(levelprefix)s %(name)s: %(message)s', use_colors=None)
    except ImportError:  # pragma: no cover — uvicorn always present at runtime
        fmt = logging.Formatter('%(levelname)-8s %(name)s: %(message)s')

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(fmt)
    logging.basicConfig(level=level, handlers=[handler], force=True)
