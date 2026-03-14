"""TX -- Message envelope for the actor system.

Every message in the system is a TX with name (event type), source, target,
data, meta, timestamp, and uuid. Same semantics as frontend TX.js.

Success = reply(). Failure = error(). The 200-OK anti-pattern is eliminated
by construction: model methods return tx.reply() or tx.error(), never
ambiguous strings.
"""

import time
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class TX:
    name: str          # Event type: SCHEMA, READ, CREATE, UPDATE, DELETE, ERROR...
    source: str        # Sender address
    target: str        # Recipient address
    data: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    uuid: str = field(default_factory=lambda: uuid4().hex[:12])

    def reply(self, data=None, name=None) -> 'TX':
        """Create a response TX with source/target swapped.
        Gets a new uuid; stores original uuid in meta['req']."""
        return TX(
            name=name or f'{self.name}_RESPONSE',
            source=self.target,
            target=self.source,
            data=data if data is not None else {},
            meta={**self.meta, 'req': self.uuid},
        )

    def error(self, message: str, code: int = 500) -> 'TX':
        """Create an error response TX."""
        return TX(
            name='ERROR',
            source=self.target,
            target=self.source,
            data={'message': message, 'code': code},
            meta={**self.meta, 'req': self.uuid, 'error': True},
        )

    def chunk(self, data, seq: int) -> 'TX':
        """Create a stream chunk reply."""
        return TX(
            name='STREAM',
            source=self.target, target=self.source,
            data=data if isinstance(data, dict) else {'chunk': data},
            meta={**self.meta, 'req': self.uuid, 'stream': True, 'seq': seq},
        )

    def end(self, data=None, seq: int = 0) -> 'TX':
        """Create a stream-end reply."""
        return TX(
            name='STREAM',
            source=self.target, target=self.source,
            data=data if data is not None else {},
            meta={**self.meta, 'req': self.uuid, 'stream': True, 'stream_end': True, 'seq': seq},
        )

    # Backward-compat aliases (deprecated — use chunk/end)
    stream_chunk = chunk
    stream_end = end

    def exception(self, e: Exception) -> 'TX':
        """Map an exception to an error TX with semantic HTTP code."""
        return TX.from_exception(e, self)

    @staticmethod
    def from_exception(e: Exception, tx: 'TX') -> 'TX':
        """Map exception types to TX error responses with semantic HTTP codes.

        Centralizes the exception → error TX translation for CRUD,
        custom method dispatch, and generic Actor handler paths.
        """
        from n3tx.core.utils.erroring import MethodError

        if isinstance(e, MethodError):
            return tx.error(e.message, code=e.status_code)
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            # HTTPException from FastAPI
            return tx.error(e.detail, code=e.status_code)

        from pydantic import ValidationError
        if isinstance(e, ValidationError):
            return tx.error(str(e), code=422)
        if isinstance(e, (ValueError, TypeError)):
            return tx.error(str(e), code=400)
        if isinstance(e, PermissionError):
            return tx.error(str(e), code=403)
        if isinstance(e, KeyError):
            return tx.error(f"Missing required field: {e}", code=400)
        return tx.error(str(e), code=500)

    @property
    def is_error(self) -> bool:
        return self.name == 'ERROR' or self.meta.get('error', False)


# Backward-compat alias (deprecated — use TX.from_exception or tx.exception)
exception_to_tx_error = TX.from_exception
