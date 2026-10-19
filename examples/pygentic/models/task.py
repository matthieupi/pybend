from __future__ import annotations
from typing import ClassVar, Literal, Optional
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route


class Task(ActorModel):
    """A task with agent-powered analysis."""

    __tablename__: ClassVar[str] = 'tasks'
    __storable__: ClassVar[bool] = True
    __agent__: ClassVar = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['title', 'status', 'priority', 'description', 'assignee'],
    }

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    status: Literal['open', 'in_progress', 'done'] = Field(default='open')
    priority: Literal['low', 'medium', 'high', 'critical'] = Field(default='medium')
    assignee: str = Field(default='')
    user_owner: Optional[int] = Field(default=None)

    @expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED)
    async def analyze(self, task: str = '', user=None):
        """Analyze this task using agent reasoning."""
        query = task or f'Analyze this task: {self.title}. {self.description}'
        async for chunk in self.agentic_stream(task=query, user=user):
            yield chunk
