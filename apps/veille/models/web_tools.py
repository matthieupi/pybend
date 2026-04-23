"""WebTools — non-storable actor providing web scraping tools for agents."""
from __future__ import annotations
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import re
from typing import ClassVar

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED

from playwright.async_api import async_playwright

from models.grant import Grant


# ── HTML-to-text extractor (stdlib, no dependencies) ──────────────

class _TextExtractor(HTMLParser):
    """Extract readable text from HTML, stripping scripts/styles/nav."""
    _SKIP_TAGS = frozenset({'script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript'})

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)


def _html_to_text(html: str) -> str:
    """Extract readable text from HTML, stripping scripts/styles."""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass  # Malformed HTML — return what we got
    return ' '.join(extractor._parts)


def _normalize_scraped_text(text: str) -> str:
    """Normalize extracted text so hashes compare meaningful content."""
    return re.sub(r'\s+', ' ', (text or '')).strip()


def _hash_scraped_text(text: str) -> str | None:
    """Return a stable content hash for normalized scraped text."""
    normalized = _normalize_scraped_text(text)
    if not normalized:
        return None
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


async def _fetch_http_content(url: str) -> dict:
    """Fetch URL content over HTTP and return normalized scrape payload."""
    import httpx

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; VeilleBot/1.0)'}
        ) as client:
            resp = await client.get(url)
        text = _normalize_scraped_text(_html_to_text(resp.text))
        return {
            'url': url,
            'final_url': str(resp.url),
            'status': resp.status_code,
            'text': text[:20000],
            'truncated': len(text) > 20000,
            'error': '',
            'method': 'scrape',
        }
    except Exception as e:
        return {
            'url': url,
            'final_url': url,
            'status': 0,
            'text': '',
            'truncated': False,
            'error': str(e),
            'method': 'scrape',
        }


async def _fetch_js_content(url: str) -> dict:
    """Fetch JS-rendered URL content via Playwright."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=30000, wait_until='networkidle')
            html = await page.content()
            final_url = page.url
            await browser.close()
        text = _normalize_scraped_text(_html_to_text(html))
        return {
            'url': url,
            'final_url': final_url,
            'status': 200,
            'text': text[:20000],
            'truncated': len(text) > 20000,
            'error': '',
            'method': 'scrape_js',
        }
    except Exception as e:
        return {
            'url': url,
            'final_url': url,
            'status': 0,
            'text': '',
            'truncated': False,
            'error': str(e),
            'method': 'scrape_js',
        }


def _persist_source_scrape(source_id: int, scrape: dict):
    """Persist scrape result onto a Source and return the updated record."""
    from models.source import Source

    existing = Source.get(source_id)
    if not existing:
        return scrape

    now = datetime.now(timezone.utc).isoformat()
    previous_hash = getattr(existing, 'scraped_content_hash', None)
    new_hash = _hash_scraped_text(scrape.get('text', ''))
    changed = bool(previous_hash and new_hash and previous_hash != new_hash)
    first_capture = bool(new_hash and not previous_hash)

    update_data = {
        'last_scraped': now,
        'scraped_content': scrape.get('text', ''),
        'scraped_content_hash': new_hash,
        'previous_content_hash': previous_hash,
        'scrape_status': scrape.get('status'),
        'scrape_method': scrape.get('method'),
        'scraped_final_url': scrape.get('final_url') or scrape.get('url'),
        'scrape_changed': changed,
        'content_updated_at': now if (changed or first_capture) else getattr(existing, 'content_updated_at', None),
        'last_scrape_error': scrape.get('error', ''),
    }

    updated = Source.update(source_id, update_data)
    return updated.model_response() if hasattr(updated, 'model_response') else updated


# ── WebTools Actor ────────────────────────────────────────────────

class WebTools(ActorModel):
    """Utility actor providing web scraping tools for agents.

    Non-storable: no DB table, no CRUD routes. Registered in Matrix
    so agents can discover and call its methods as tools.
    """
    __tablename__: ClassVar[str] = 'web_tools'
    __storable__: ClassVar[bool] = False
    __ui__: ClassVar[dict] = {'icon': 'veille-tools'}

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(url: str, source_id: int | None = None) -> dict:
        """Fetch a URL via HTTP and return its text content.

        Uses httpx with redirect following. Returns extracted text
        (HTML tags stripped). Good for server-rendered pages.
        Truncates to 20000 chars to stay within tool result limits.
        """
        result = await _fetch_http_content(url)
        return _persist_source_scrape(source_id, result) if source_id else result

    @expose_route('/scrape_js', methods=['POST'], access=AUTHENTICATED)
    async def scrape_js(url: str, source_id: int | None = None) -> dict:
        """Fetch a JS-rendered page using Playwright headless browser.

        Use this when scrape() returns empty/minimal content,
        indicating the page requires JavaScript to render.
        """
        result = await _fetch_js_content(url)
        return _persist_source_scrape(source_id, result) if source_id else result

    @expose_route('/check_duplicate', methods=['POST'], access=AUTHENTICATED)
    def check_duplicate(url: str, title: str = '') -> dict:
        """Check if a grant already exists by URL match.

        Returns {duplicate: True, id: N, method: 'url'} if found,
        or {duplicate: False} if no match. The agent can use LLM
        reasoning for title-based comparison when URL doesn't match.
        """
        try:
            existing = Grant.list(limit=200)
            data = existing.get('data', existing) if isinstance(existing, dict) else existing
            for grant in data:
                g = grant if isinstance(grant, dict) else grant.model_dump() if hasattr(grant, 'model_dump') else {}
                # Check primary URL
                if url and g.get('url') == url:
                    return {'duplicate': True, 'id': g.get('id'), 'method': 'url'}
                # Check source_url
                if url and g.get('source_url') == url:
                    return {'duplicate': True, 'id': g.get('id'), 'method': 'source_url'}
                # Check source_urls list
                if url and url in (g.get('source_urls') or []):
                    return {'duplicate': True, 'id': g.get('id'), 'method': 'source_urls'}
        except Exception as e:
            return {'duplicate': False, 'error': str(e)}
        return {'duplicate': False}
