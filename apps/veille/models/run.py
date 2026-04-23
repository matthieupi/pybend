"""Run — scraping run model with deterministic per-source execution."""
from __future__ import annotations
import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import ClassVar, Optional

from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField

from models.grant import Grant
from models.source import Source

logger = logging.getLogger('veille.run')


# ── Stream event models ────────────────────────────────────────────

class SourceStartEvent(ProtoModel):
    source_id: Optional[int] = None
    name: str = ''
    url: str = ''
    index: int = 0
    total: int = 0


class SourceDoneEvent(ProtoModel):
    source_id: Optional[int] = None
    grants_found: int = 0


class GrantFoundEvent(ProtoModel):
    id: int = 0
    title: str = ''
    url: str = ''


# ── Module-level helpers ───────────────────────────────────────────

def _get(obj, key, default=None):
    """Uniform access for dict or object."""
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _resolve_user_dict(user):
    """Convert user (model instance, dict, or None) to agent-pipeline dict."""
    if user is None:
        return None
    if hasattr(user, 'model_dump'):
        ud = user.model_dump()
        return {'user_id': ud.get('id'), 'email': ud.get('email'), 'role': ud.get('role', 'user')}
    return user if isinstance(user, dict) else None


def _get_active_sources():
    """Return all active sources as dicts."""
    sources = Source.list(limit=200)
    data = sources.get('data', sources) if isinstance(sources, dict) else sources
    return [s if isinstance(s, dict) else s.model_dump() for s in data
            if _get(s, 'active', True)]


def _get_discovered_sources(processed_ids, processed_urls):
    """Return agent-discovered sources not yet processed."""
    sources = Source.list(limit=500)
    data = sources.get('data', sources) if isinstance(sources, dict) else sources
    result = []
    for s in data:
        d = s if isinstance(s, dict) else s.model_dump()
        if (_get(d, 'agent_discovered')
                and _get(d, 'id') not in processed_ids
                and _get(d, 'url', '') not in processed_urls):
            result.append(d)
    return result


def _get_grant_ids_for_run(run_id):
    """Return set of grant IDs linked to a run."""
    grants = Grant.list(sql_filter=('run_id = ?', [run_id]), limit=1000)
    data = grants.get('data', grants) if isinstance(grants, dict) else grants
    return {_get(g, 'id') for g in data}


# ── Events dict shared by execute() and adhoc() ───────────────────

_STREAM_EVENTS = {
    'text': TextChunk,
    'tool_call': ToolCallEvent,
    'tool_result': ToolResultEvent,
    'thinking': ThinkingChunk,
    'done': DoneChunk,
    'source_start': SourceStartEvent,
    'source_done': SourceDoneEvent,
    'grant_found': GrantFoundEvent,
}


class Run(ActorModel):
    """A scraping run — each execution is a stored record with agent capabilities.

    Lifecycle: pending -> running -> complete/failed
    Types: 'full' (all active sources) or 'adhoc' (single URL scan)
    """
    __tablename__: ClassVar[str] = 'runs'
    __storable__: ClassVar[bool] = True
    __agent__: ClassVar[dict] = {
        'self_tools': False,
        'neighbors': False,
        'tools': ['web_tools', 'grants', 'sources'],
    }
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'icon': 'veille-run',
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
            'execute': {'renderer': 'ntx-run-output', 'icon': 'veille-execute'},
            'adhoc': {'renderer': 'ntx-run-output', 'icon': 'veille-adhoc'},
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
        run_record = Run.get(run_id)
        run_meta = run_record if isinstance(run_record, dict) else (
            run_record.model_dump() if hasattr(run_record, 'model_dump') else {}
        )

        grants = Grant.list(sql_filter=('run_id = ?', [run_id]), limit=1000)
        data = grants.get('data', grants) if isinstance(grants, dict) else grants

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

        admissible.sort(key=lambda g: (g.get('admissibility_score') or 0.0), reverse=True)
        partially_admissible.sort(key=lambda g: (g.get('admissibility_score') or 0.0), reverse=True)

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

    # ── Public streaming endpoints ─────────────────────────────────

    @expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events=_STREAM_EVENTS)
    async def execute(self, user=None):
        """Execute full run: scrape ALL active sources. Streams progress."""
        user_dict = _resolve_user_dict(user)
        self._mark_running('full')

        try:
            sources = _get_active_sources()
            if not sources:
                yield {'name': 'error', 'data': {'message': 'No active sources configured'}}
                self._mark_failed(Exception('No active sources configured'))
                return
            Run.update(self.id, {'sources_covered': len(sources)})

            work_queue = deque(sources)
            async for chunk in self._process_queue(work_queue, user_dict):
                yield chunk

        except Exception as e:
            self._mark_failed(e)
            raise

    @expose_route('/adhoc', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events=_STREAM_EVENTS)
    async def adhoc(self, url: str, user=None):
        """Scan a single URL. Streams progress."""
        user_dict = _resolve_user_dict(user)
        Run.update(self.id, {'adhoc_url': url})
        self._mark_running('adhoc')

        try:
            synthetic = {'id': None, 'url': url, 'name': url,
                         'language': 'en', 'scraping_notes': ''}
            work_queue = deque([synthetic])
            async for chunk in self._process_queue(work_queue, user_dict, adhoc=True):
                yield chunk

        except Exception as e:
            self._mark_failed(e)
            raise

    # ── Core loop ──────────────────────────────────────────────────

    async def _process_queue(self, work_queue, user_dict, adhoc=False):
        """Deterministic loop: drain work queue, scraping one source at a time."""
        processed_ids = set()
        processed_urls = set()
        total_grants = 0
        prompt = self._build_prompt()

        while work_queue:
            source = work_queue.popleft()
            sid = _get(source, 'id')
            url = _get(source, 'url', '')

            # Dedup
            if (sid and sid in processed_ids) or url in processed_urls:
                continue
            if sid:
                processed_ids.add(sid)
            processed_urls.add(url)

            yield {'name': 'source_start', 'data': {
                'source_id': sid,
                'name': _get(source, 'name', url),
                'url': url,
                'index': len(processed_ids) + len(processed_urls) - (1 if sid else 0),
                'total': len(processed_ids) + len(processed_urls) + len(work_queue) - (1 if sid else 0),
            }}

            # Scrape source — yields agent stream chunks, stores new grants on self
            async for chunk in self._scrape_source(source, prompt, user_dict):
                yield chunk
            new_grants = getattr(self, '_last_scrape_grants', [])
            total_grants += len(new_grants)

            # Enqueue newly discovered sources (full runs only)
            if not adhoc:
                for s in _get_discovered_sources(processed_ids, processed_urls):
                    work_queue.append(s)

            # Update last_scraped timestamp on source
            if sid:
                Source.update(sid, {'last_scraped': datetime.now(timezone.utc).isoformat()})

            yield {'name': 'source_done', 'data': {
                'source_id': sid,
                'grants_found': len(new_grants),
            }}

        self._mark_complete(total_grants, len(processed_ids) + len(processed_urls))

    # ── Per-source scraping ────────────────────────────────────────

    async def _scrape_source(self, source, prompt, user_dict):
        """Scrape a single source via focused agent. Yields stream chunks."""
        task = self._build_source_task(source)
        grants_before = _get_grant_ids_for_run(self.id)

        async for chunk in self.agentic_stream(task=task, prompt=prompt, user=user_dict):
            yield chunk

        grants_after = _get_grant_ids_for_run(self.id)
        new_grant_ids = list(grants_after - grants_before)

        for gid in new_grant_ids:
            g = Grant.get(gid)
            yield {'name': 'grant_found', 'data': {
                'id': gid,
                'title': _get(g, 'title', ''),
                'url': _get(g, 'url', ''),
            }}

        # Store for caller to read (async generators can't return values)
        self._last_scrape_grants = new_grant_ids

    # ── Status transitions ─────────────────────────────────────────

    def _mark_running(self, run_type):
        Run.update(self.id, {
            'status': 'running',
            'type': run_type,
            'started_at': datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Run {self.id} started (type={run_type})")

    def _mark_complete(self, grants_found, sources_covered):
        Run.update(self.id, {
            'status': 'complete',
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'grants_found': grants_found,
            'sources_covered': sources_covered,
        })
        logger.info(f"Run {self.id} complete ({grants_found} grants)")

    def _mark_failed(self, error):
        logger.error(f"Run {self.id} failed: {error}")
        Run.update(self.id, {
            'status': 'failed',
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'error': str(error),
        })

    # ── Lifecycle handler — auto-analyze grants created outside runs ──

    @classmethod
    async def LIFECYCLE(cls, data, tx):
        """Auto-analyze grants created without a run_id."""
        if data.get('event') != 'after_create':
            return
        entity = data.get('entity', {})
        grant_id = entity.get('id')
        if not grant_id or entity.get('run_id'):
            return  # Part of a run — UI or scheduler handles analysis
        asyncio.create_task(cls._analyze_grant_background(grant_id))

    @staticmethod
    async def _analyze_grant_background(grant_id):
        """Non-streaming grant analysis for manual creates + scheduler."""
        from models.organization import Organization
        try:
            orgs = Organization.list(limit=1)
            org_data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
            if not org_data:
                return
            raw = Grant.get(grant_id)
            if not raw:
                return
            grant = raw if not isinstance(raw, dict) else Grant(**{k: v for k, v in raw.items()})
            Grant.update(grant_id, {'status': 'analyzing'})
            await grant.agentic(
                task=grant._build_analysis_task(),
                prompt=grant._build_analysis_prompt(),
            )
            logger.info(f"Background analysis complete for grant {grant_id}")
        except Exception as e:
            logger.warning(f"Background analysis failed for grant {grant_id}: {e}")
            Grant.update(grant_id, {'status': 'new'})

    # ── Task/prompt construction ───────────────────────────────────

    def _build_source_task(self, source) -> str:
        """Focused task for scraping ONE source."""
        name = _get(source, 'name', '')
        url = _get(source, 'url', '')
        lang = _get(source, 'language', 'en')
        notes = _get(source, 'scraping_notes', '')
        sid = _get(source, 'id', '')

        lines = [
            "Scrape this source and extract all grant/funding opportunities:",
            "",
            f"Source: {name}",
            f"URL: {url}",
            f"Language: {lang}",
        ]
        if notes:
            lines.append(f"Scraping notes: {notes}")
        if sid:
            fetch_steps = [
                f"1. Call sources_fetch with id={sid} to fetch and persist the latest source content.",
                "2. Read the returned source.scraped_content. If it is empty or clearly incomplete,",
                f"   call sources_fetch again with id={sid} and use_js=true.",
                "3. Identify grants or funding programs from the fetched content.",
            ]
        else:
            fetch_steps = [
                "1. Use web_tools_scrape to fetch the page. If empty, try web_tools_scrape_js.",
                "2. Read the content. Identify grants or funding programs.",
            ]
        lines += [
            "",
            "Steps:",
            *fetch_steps,
            "4. For each grant found:",
            "   a. Call web_tools_check_duplicate with the grant URL.",
            f"   b. If NOT duplicate, call grants_create. Set run_id={self.id}"
            + (f", source_id={sid}" if sid else "") + ".",
            "   c. Extract: title, funder, url, source_url, description, amount_min/max,",
            "      deadline, eligibility_criteria, required_documents, application_process, language.",
            "5. If you find links to OTHER grant portals/directories,",
            "   call sources_create (set agent_discovered=true, active=true).",
            "6. Follow detail links for full grant information using web_tools_scrape or web_tools_scrape_js.",
        ]
        return '\n'.join(lines)

    def _build_prompt(self) -> str:
        """System prompt with org context. Reused across all source agents."""
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
