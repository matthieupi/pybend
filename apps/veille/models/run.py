"""Run — scraping run model with agentic execution."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import ClassVar, Optional

from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField

from models.grant import Grant

logger = logging.getLogger('veille.run')


class Run(ActorModel):
    """A scraping run — each execution is a stored record with agent capabilities.

    Lifecycle: pending -> running -> complete/failed
    Types: 'full' (all active sources) or 'adhoc' (single URL scan)
    """
    __tablename__: ClassVar[str] = 'runs'
    __storable__: ClassVar[bool] = True
    __agent__: ClassVar[dict] = {
        'self_tools': False,   # Run doesn't need CRUD on itself
        'neighbors': False,    # No ListRef neighbors
        'tools': ['web_tools', 'grants', 'sources'],  # Explicit tool list
    }
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': [
            'status', 'type', 'started_at', 'completed_at',
            'grants_found', 'sources_covered', 'adhoc_url', 'error',
        ],
        'groups': {
            'Status': ['status', 'type', 'started_at', 'completed_at'],
            'Results': ['grants_found', 'sources_covered'],
            'Config': ['adhoc_url'],
            'Errors': ['error'],
        },
        'renderer': {'item': 'ntx-run-item'},
        'methods': {
            'execute': {'renderer': 'ntx-stream-agent'},
        },
    }

    # Lifecycle
    status: str = Field(default='pending')
    type: str = Field(default='full')
    started_at: Optional[str] = Field(default=None)
    completed_at: Optional[str] = Field(default=None)

    # Results
    grants_found: int = Field(default=0)
    sources_covered: int = Field(default=0)

    # Config
    adhoc_url: str = Field(default='')

    # Error tracking
    error: TextareaField = Field(default='')

    # ── Report endpoint (class-level, no self) ───────────────────

    @expose_route('/report', methods=['GET'], access=AUTHENTICATED)
    def report(run_id: int) -> dict:
        """Return grants for a run grouped by admissibility status.

        Route: GET /runs/report?run_id=N
        """

        # Fetch run metadata
        run_record = Run.get(run_id)
        run_meta = run_record if isinstance(run_record, dict) else (
            run_record.model_dump() if hasattr(run_record, 'model_dump') else {}
        )

        # Fetch all grants for this run
        grants = Grant.list(sql_filter=('run_id = ?', [run_id]), limit=1000)
        data = grants.get('data', grants) if isinstance(grants, dict) else grants

        # Group by status
        admissible = []
        partially_admissible = []
        non_admissible = []
        new_grants = []

        for g in data:
            gd = g if isinstance(g, dict) else (g.model_dump() if hasattr(g, 'model_dump') else {})
            status = gd.get('status', 'new')
            if status == 'admissible':
                admissible.append(gd)
            elif status == 'partially admissible':
                partially_admissible.append(gd)
            elif status == 'non-admissible':
                non_admissible.append(gd)
            else:
                new_grants.append(gd)

        # Sort scored buckets by admissibility_score descending (Python-side)
        admissible.sort(
            key=lambda g: (g.get('admissibility_score') or 0.0),
            reverse=True,
        )
        partially_admissible.sort(
            key=lambda g: (g.get('admissibility_score') or 0.0),
            reverse=True,
        )

        total = len(admissible) + len(partially_admissible) + len(non_admissible) + len(new_grants)
        return {
            'run_id': run_id,
            'run': run_meta,
            'admissible': admissible,
            'partially_admissible': partially_admissible,
            'non_admissible': non_admissible,
            'new': new_grants,
            'counts': {
                'admissible': len(admissible),
                'partially_admissible': len(partially_admissible),
                'non_admissible': len(non_admissible),
                'new': len(new_grants),
                'total': total,
            },
        }

    # ── Streaming execute endpoint ────────────────────────────────

    @expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events={
                      'text': TextChunk,
                      'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent,
                      'thinking': ThinkingChunk,
                      'done': DoneChunk,
                  })
    async def execute(self, adhoc_url: str = '', user=None):
        """Execute the scraping run. Streams agent progress as SSE events.

        For full runs: scrapes all active sources.
        For adhoc runs: scrapes the provided URL only.

        The agent uses tool calls to:
        - web_tools_scrape / web_tools_scrape_js: fetch page content
        - web_tools_check_duplicate: check if grant already exists
        - grants_create: create new grant records
        - sources_list: read configured sources
        - sources_create: add newly discovered sources
        """
        now = datetime.now(timezone.utc).isoformat()

        # If adhoc_url provided, override the stored value
        if adhoc_url:
            self.adhoc_url = adhoc_url
            self.type = 'adhoc'

        # Update status to running
        Run.update(self.id, {
            'status': 'running',
            'started_at': now,
            'type': self.type,
            'adhoc_url': self.adhoc_url,
        })
        logger.info(f"Run {self.id} started (type={self.type})")

        # Resolve user to a dict for the agent pipeline (could be User instance, dict, or None)
        user_dict = None
        if user is not None:
            if hasattr(user, 'model_dump'):
                ud = user.model_dump()
                user_dict = {'user_id': ud.get('id'), 'email': ud.get('email'), 'role': ud.get('role', 'user')}
            elif isinstance(user, dict):
                user_dict = user
        task = self._build_task()
        prompt = self._build_prompt()

        try:
            async for chunk in self.agentic_stream(task=task, prompt=prompt, user=user_dict):
                yield chunk

            # Count grants created during this run
            from models.grant import Grant
            _run_grants_data = []
            try:
                grants = Grant.list(limit=1000)
                _run_grants_data = grants.get('data', grants) if isinstance(grants, dict) else grants
                count = sum(1 for g in _run_grants_data
                            if (g.get('run_id') if isinstance(g, dict)
                                else getattr(g, 'run_id', None)) == self.id)
            except Exception:
                count = 0

            # ── Batch admissibility analysis ─────────────────────────────
            # Analyze each newly discovered grant against the org profile.
            # Uses non-streaming agentic() -- the SSE stream to the client
            # is already done at this point.
            new_grants = [g for g in _run_grants_data
                          if (g.get('run_id') if isinstance(g, dict)
                              else getattr(g, 'run_id', None)) == self.id
                          and (g.get('status') if isinstance(g, dict)
                               else getattr(g, 'status', 'new')) == 'new']

            # Check org exists before batch
            from models.organization import Organization
            try:
                orgs = Organization.list(limit=1)
                org_data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
            except Exception:
                org_data = []

            if org_data:
                for i, grant_record in enumerate(new_grants):
                    grant_id = (grant_record.get('id') if isinstance(grant_record, dict)
                                else getattr(grant_record, 'id', None))
                    if not grant_id:
                        continue
                    try:
                        raw = Grant.get(grant_id)
                        if isinstance(raw, dict):
                            grant_instance = Grant(**{k: v for k, v in raw.items()})
                        else:
                            grant_instance = raw

                        await grant_instance.agentic(
                            task=grant_instance._build_analysis_task(),
                            prompt=grant_instance._build_analysis_prompt(),
                            user=user_dict,
                        )
                        logger.info(f"Analyzed grant {grant_id} ({i+1}/{len(new_grants)})")
                    except Exception as e:
                        logger.warning(f"Analysis failed for grant {grant_id}: {e}")
            else:
                logger.warning("No org profile configured -- skipping batch analysis")

            Run.update(self.id, {
                'status': 'complete',
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'grants_found': count,
            })
            logger.info(f"Run {self.id} complete ({count} grants found)")

        except Exception as e:
            logger.error(f"Run {self.id} failed: {e}")
            Run.update(self.id, {
                'status': 'failed',
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'error': str(e),
            })
            raise

    # ── Prompt construction ───────────────────────────────────────

    def _build_task(self) -> str:
        """Build the task description for the agent.

        For full runs: lists all active sources with their URLs and scraping notes.
        For adhoc runs: provides just the single URL.
        """
        if self.type == 'adhoc' and self.adhoc_url:
            return (
                f"Scan this URL for grant/funding opportunities: {self.adhoc_url}\n\n"
                "1. Use web_tools_scrape to fetch the page content.\n"
                "2. If the content is empty or seems JS-rendered, use web_tools_scrape_js instead.\n"
                "3. Read the page carefully. Identify any grant or funding programs.\n"
                "4. For each grant found, extract full details and use grants_create to store it.\n"
                "5. Before creating, use web_tools_check_duplicate to avoid duplicates.\n"
                f"6. Set run_id={self.id} on every grant you create.\n"
                "7. If you find links to other grant sources, use sources_create to add them "
                "(set agent_discovered=true).\n"
            )

        # Full run: gather all active sources
        from models.source import Source
        try:
            sources = Source.list(limit=100)
            data = sources.get('data', sources) if isinstance(sources, dict) else sources
            active = [s for s in data
                      if (s.get('active') if isinstance(s, dict) else getattr(s, 'active', True))]
        except Exception:
            active = []

        if not active:
            return (
                "No active sources configured. "
                "Please inform the user that they need to add at least one source "
                "before running a scraping scan."
            )

        # Update sources_covered
        Run.update(self.id, {'sources_covered': len(active)})

        source_list = []
        for i, s in enumerate(active, 1):
            if isinstance(s, dict):
                name = s.get('name', 'Unknown')
                url = s.get('url', '')
                notes = s.get('scraping_notes', '')
                sid = s.get('id', '')
                lang = s.get('language', 'en')
            else:
                name = getattr(s, 'name', 'Unknown')
                url = getattr(s, 'url', '')
                notes = getattr(s, 'scraping_notes', '')
                sid = getattr(s, 'id', '')
                lang = getattr(s, 'language', 'en')

            entry = f"Source {i}: {name}\n  URL: {url}\n  Language: {lang}\n  Source ID: {sid}"
            if notes:
                entry += f"\n  Scraping notes: {notes}"
            source_list.append(entry)

        sources_text = '\n\n'.join(source_list)

        return (
            f"Scrape all {len(active)} configured sources for grant/funding opportunities.\n\n"
            f"SOURCES:\n{sources_text}\n\n"
            "FOR EACH SOURCE:\n"
            "1. Use web_tools_scrape to fetch the source page.\n"
            "2. If content is empty or appears JS-rendered, try web_tools_scrape_js.\n"
            "3. Read the content carefully. Identify grant/funding programs.\n"
            "4. Follow links to individual grant pages for full details.\n"
            "5. For each grant found:\n"
            "   a. Use web_tools_check_duplicate with the grant URL to check for existing records.\n"
            "   b. If not a duplicate, use grants_create with ALL extracted details.\n"
            f"   c. Set run_id={self.id} and source_id=<source id> on every grant.\n"
            "   d. Extract: title, funder, url, source_url, description, amount_min, amount_max, "
            "deadline, eligibility_criteria (as list), required_documents (as list), "
            "application_process, language.\n"
            "   e. Add the source URL to source_urls list for dedup tracking.\n"
            "6. If you discover links to OTHER grant portals/sources not in the list above, "
            "use sources_create to add them (set agent_discovered=true, active=true).\n"
            "7. Be thorough but efficient. Follow promising links but don't crawl endlessly.\n"
            "8. Pay attention to scraping notes for each source — they contain human guidance.\n"
        )

    def _build_prompt(self) -> str:
        """Build the system prompt with organization context.

        Includes the organization profile (mission, criteria, focus areas)
        so the agent can extract grants relevant to the organization.
        Also includes uploaded document summaries if available.
        """
        parts = [
            "You are a grant research agent for a non-profit organization. "
            "Your job is to scrape web sources and extract grant/funding opportunities.",
            "",
            "RULES:",
            "- Always check for duplicates before creating a grant (use web_tools_check_duplicate).",
            "- Extract as much detail as possible from each grant page.",
            "- If a page is in French, extract details in the original language and set language='fr'.",
            "- Set discovered_at to the current date in ISO format.",
            "- When you find links to other grant portals, add them as new sources.",
            "- Be methodical: scrape source page, identify grants, follow detail links, extract, create.",
            "",
        ]

        # Add organization context
        from models.organization import Organization
        try:
            orgs = Organization.list(limit=1)
            data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
            if data:
                org = data[0]
                o = org if isinstance(org, dict) else org.model_dump() if hasattr(org, 'model_dump') else {}
                parts.append("ORGANIZATION PROFILE:")
                if o.get('name'):
                    parts.append(f"  Name: {o['name']}")
                if o.get('mission'):
                    parts.append(f"  Mission: {o['mission']}")
                if o.get('activities'):
                    parts.append(f"  Activities: {o['activities']}")
                if o.get('legal_status'):
                    parts.append(f"  Legal status: {o['legal_status']}")
                if o.get('province'):
                    parts.append(f"  Province: {o['province']}")
                if o.get('charitable_status'):
                    parts.append(f"  Charitable status: {o['charitable_status']}")
                if o.get('employee_count'):
                    parts.append(f"  Employees: {o['employee_count']}")
                budget = o.get('annual_budget')
                if budget is not None:
                    try:
                        parts.append(f"  Annual budget: ${float(budget):,.0f}")
                    except (TypeError, ValueError):
                        parts.append(f"  Annual budget: {budget}")
                if o.get('focus_areas'):
                    parts.append(f"  Focus areas: {', '.join(o['focus_areas'])}")
                if o.get('custom_criteria'):
                    parts.append(f"  Custom criteria: {o['custom_criteria']}")
                parts.append("")
                parts.append(
                    "Use the organization profile to identify grants that are relevant. "
                    "Extract all grants you find, not just ones that match — the admissibility "
                    "analysis happens in a later phase."
                )
                parts.append("")
        except Exception as e:
            logger.warning(f"Could not load organization profile: {e}")

        return '\n'.join(parts)
