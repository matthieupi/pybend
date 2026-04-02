"""WebTools — non-storable actor providing web scraping tools for agents."""
from __future__ import annotations
from html.parser import HTMLParser
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


# ── WebTools Actor ────────────────────────────────────────────────

class WebTools(ActorModel):
    """Utility actor providing web scraping tools for agents.

    Non-storable: no DB table, no CRUD routes. Registered in Matrix
    so agents can discover and call its methods as tools.
    """
    __tablename__: ClassVar[str] = 'web_tools'
    __storable__: ClassVar[bool] = False
    __ui__: ClassVar[dict] = {'icon': '🛠️'}

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(url: str) -> dict:
        """Fetch a URL via HTTP and return its text content.

        Uses httpx with redirect following. Returns extracted text
        (HTML tags stripped). Good for server-rendered pages.
        Truncates to 20000 chars to stay within tool result limits.
        """
        import httpx
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; VeilleBot/1.0)'}
            ) as client:
                resp = await client.get(url)
            text = _html_to_text(resp.text)
            return {
                'url': url,
                'status': resp.status_code,
                'text': text[:20000],
                'truncated': len(text) > 20000,
            }
        except Exception as e:
            return {'url': url, 'status': 0, 'text': '', 'error': str(e)}

    @expose_route('/scrape_js', methods=['POST'], access=AUTHENTICATED)
    async def scrape_js(url: str) -> dict:
        """Fetch a JS-rendered page using Playwright headless browser.

        Use this when scrape() returns empty/minimal content,
        indicating the page requires JavaScript to render.
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000, wait_until='networkidle')
                html = await page.content()
                await browser.close()
            text = _html_to_text(html)
            return {
                'url': url,
                'status': 200,
                'text': text[:20000],
                'truncated': len(text) > 20000,
            }
        except Exception as e:
            return {'url': url, 'status': 0, 'text': '', 'error': str(e)}

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
