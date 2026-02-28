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
        Gets a new uuid; stores original uuid in meta['in_reply_to']."""
        return TX(
            name=name or f'{self.name}_RESPONSE',
            source=self.target,
            target=self.source,
            data=data if data is not None else {},
            meta={**self.meta, 'in_reply_to': self.uuid},
        )

    def error(self, message: str, code: int = 500) -> 'TX':
        """Create an error response TX."""
        return TX(
            name='ERROR',
            source=self.target,
            target=self.source,
            data={'message': message, 'code': code},
            meta={**self.meta, 'in_reply_to': self.uuid, 'error': True},
        )

    @property
    def is_error(self) -> bool:
        return self.name == 'ERROR' or self.meta.get('error', False)
