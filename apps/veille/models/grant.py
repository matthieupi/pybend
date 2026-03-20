from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField, MarkdownField


class Grant(ActorModel):
    __tablename__: ClassVar[str] = 'grants'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': [
            'title', 'funder', 'status', 'url', 'source_url',
            'amount_min', 'amount_max', 'deadline',
            'description', 'eligibility_criteria',
            'required_documents', 'application_process',
            'admissibility_score', 'admissibility_reasoning',
        ],
        'groups': {
            'Overview': ['title', 'funder', 'status', 'url', 'source_url'],
            'Funding': ['amount_min', 'amount_max', 'deadline'],
            'Details': ['description', 'eligibility_criteria',
                        'required_documents', 'application_process'],
            'Analysis': ['admissibility_score', 'admissibility_reasoning'],
        },
    }

    # Core identification
    title: str = Field(min_length=1, max_length=500)
    funder: str = Field(default='')
    url: str = Field(default='')
    source_url: str = Field(default='')

    # Details
    description: TextareaField = Field(default='')
    amount_min: Optional[float] = Field(default=None)
    amount_max: Optional[float] = Field(default=None)
    deadline: Optional[str] = Field(default=None)
    eligibility_criteria: list = Field(default_factory=list)
    required_documents: list = Field(default_factory=list)
    application_process: TextareaField = Field(default='')

    # Admissibility (set by analysis agent in Phase 3)
    status: str = Field(default='new')
    admissibility_score: Optional[float] = Field(default=None)
    admissibility_reasoning: MarkdownField = Field(default='')

    # Metadata
    language: str = Field(default='en')
    discovered_at: Optional[str] = Field(default=None)
    run_id: Optional[int] = Field(default=None)
    source_id: Optional[int] = Field(default=None)
