from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField


class Organization(ActorModel):
    __tablename__: ClassVar[str] = 'organizations'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': ROLE('admin'),
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'icon': '🏢',
        'field_order': [
            'name', 'mission', 'activities', 'legal_status',
            'province', 'charitable_status',
            'employee_count', 'annual_budget',
            'focus_areas', 'custom_criteria', 'documents',
            'schedule_enabled', 'schedule_interval_hours',
        ],
        'groups': {
            'Identity': ['name', 'mission', 'activities'],
            'Legal': ['legal_status', 'province', 'charitable_status'],
            'Size': ['employee_count', 'annual_budget'],
            'Eligibility': ['focus_areas', 'custom_criteria'],
            'Documents': ['documents'],
            'Schedule': ['schedule_enabled', 'schedule_interval_hours'],
        },
    }

    # Identity
    name: str = Field(min_length=1, max_length=300)
    mission: TextareaField = Field(default='')
    activities: TextareaField = Field(default='')

    # Legal/location
    legal_status: str = Field(default='')
    province: str = Field(default='')
    charitable_status: str = Field(default='')

    # Size
    employee_count: Optional[int] = Field(default=None)
    annual_budget: Optional[float] = Field(default=None)

    # Eligibility context (JSON fields -- auto-serialized by SQLite storage)
    focus_areas: list = Field(default_factory=list)
    custom_criteria: dict = Field(default_factory=dict)

    # Document references (list of filenames stored on disk)
    documents: list = Field(default_factory=list)

    # Scheduling configuration
    schedule_enabled: bool = Field(default=False)
    schedule_interval_hours: int = Field(
        default=168,
        json_schema_extra={'ui': {'placeholder': 'Hours between runs (168 = weekly)'}},
    )
