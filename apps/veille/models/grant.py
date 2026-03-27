from __future__ import annotations
import logging
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField, MarkdownField

from models.organization import Organization

logger = logging.getLogger('veille.grant')


class Grant(ActorModel):
    __tablename__: ClassVar[str] = 'grants'
    __storable__: ClassVar[bool] = True
    _subscribers: ClassVar[list] = ['runs']
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
        'renderer': {'item': 'ntx-grant-item'},
        'methods': {
            'analyze': {'renderer': 'ntx-grant-analyze'},
        },
    }
    __agent__: ClassVar[dict] = {
        'self_tools': True,          # grants_update saves analysis results
        'neighbors': False,
        'tools': ['organizations'],  # organizations_list reads org profile
    }

    # Core identification
    title: str = Field(min_length=1, max_length=500)
    funder: str = Field(default='')
    url: str = Field(default='')
    source_url: str = Field(default='')

    # Dedup tracking: all source URLs where this grant was found
    # Hidden from UI — internal tracking only. SQLite auto-serializes list to JSON TEXT.
    source_urls: list = Field(default_factory=list,
                              json_schema_extra={'ui': {'display': False}})

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

    # ── Streaming analyze endpoint ─────────────────────────────────

    @expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events={
                      'text': TextChunk,
                      'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent,
                      'thinking': ThinkingChunk,
                      'done': DoneChunk,
                  })
    async def analyze(self, user=None):
        """Analyze this grant's admissibility against the org profile. Streams progress.
        Route: POST /grants/{id}/analyze
        """
        try:
            orgs = Organization.list(limit=1)
            data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
        except Exception:
            data = []
        if not data:
            raise LookupError('No organization found to analyze the grant against')

        # Resolve user to dict for agent pipeline
        user_dict = None
        if user is not None:
            if hasattr(user, 'model_dump'):
                ud = user.model_dump()
                user_dict = {'user_id': ud.get('id'), 'email': ud.get('email'), 'role': ud.get('role', 'user')}
            elif isinstance(user, dict):
                user_dict = user

        task = self._build_analysis_task()
        prompt = self._build_analysis_prompt()
        Grant.update(self.id, {'status': 'analyzing'})
        try:
            async for chunk in self.agentic_stream(task=task, prompt=prompt, user=user_dict):
                yield chunk
        except Exception as e:
            logger.error(f"Analysis failed for grant {self.id}: {e}")
            Grant.update(self.id, {'status': 'new'})
            raise

    # ── Analysis prompt construction ──────────────────────────────

    def _build_analysis_task(self) -> str:
        """Build the task description for the admissibility agent."""
        criteria_str = (
            '\n'.join(f'  - {c}' for c in self.eligibility_criteria)
            if self.eligibility_criteria else '  (none listed)'
        )
        return (
            f"Analyze admissibility of this grant for our organization.\n\n"
            f"GRANT DETAILS:\n"
            f"  Title: {self.title}\n"
            f"  Funder: {self.funder}\n"
            f"  Description: {(self.description or '')[:800]}\n"
            f"  Eligibility criteria:\n{criteria_str}\n"
            f"  Amount: {self.amount_min} to {self.amount_max}\n"
            f"  Deadline: {self.deadline}\n\n"
            f"STEPS:\n"
            f"1. Call organizations_list to read the organization profile.\n"
            f"2. For each eligibility criterion, check if the org meets it.\n"
            f"3. Determine the classification:\n"
            f"   - 'admissible': org meets all or nearly all criteria\n"
            f"   - 'partially admissible': org meets some but not all\n"
            f"   - 'non-admissible': org does not meet key criteria\n"
            f"4. Write a Markdown justification referencing specific criteria.\n"
            f"5. Assign a score from 0.0 (inadmissible) to 1.0 (fully admissible).\n"
            f"6. Call grants_update with: id={self.id}, status=<classification>, "
            f"admissibility_score=<float 0.0-1.0>, admissibility_reasoning=<markdown>.\n"
        )

    def _build_analysis_prompt(self) -> str:
        """Build the system prompt for the admissibility agent."""
        return (
            "You are a grant admissibility analyst for a non-profit organization. "
            "Your job is to evaluate whether a grant matches the organization's eligibility profile.\n\n"
            "RULES:\n"
            "- Always call organizations_list FIRST to read the live organization profile.\n"
            "- Classification must be exactly one of: 'admissible', 'partially admissible', 'non-admissible'.\n"
            "- Score is a float from 0.0 to 1.0 (NOT a percentage). 0.0 = completely inadmissible, 1.0 = fully admissible.\n"
            "- Reasoning must be in Markdown format. Include a section per criterion.\n"
            "- Always call grants_update to save your results before finishing.\n"
            "- Be specific: cite which profile fields match or fail which criteria.\n"
        )
