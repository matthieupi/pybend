from __future__ import annotations
from typing import ClassVar

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED


class WebTools(ActorModel):
    """Utility actor providing web scraping tools for agents."""

    __tablename__: ClassVar[str] = 'web_tools'
    __storable__: ClassVar[bool] = False

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return its HTML content."""
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
        return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}

    @expose_route('/extract', methods=['POST'], access=AUTHENTICATED)
    def extract(self, html: str, selector: str = 'body') -> dict:
        """Extract text from HTML using CSS selectors."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.select(selector)
        return {
            'count': len(elements),
            'texts': [el.get_text(strip=True) for el in elements[:20]],
        }
