"""Uniform page fetcher: try Firecrawl first, fall back to Browserbase."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from .browserbase_client import BrowserbaseClient, BrowserbaseError
from .firecrawl_client import FirecrawlClient, FirecrawlError

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    markdown: str
    html: str
    title: str | None
    source_engine: str
    metadata: dict[str, Any]


def _html_to_markdown(html: str) -> str:
    """Last-ditch markdown approximation when only HTML is available."""
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return text


async def fetch_page(
    url: str,
    *,
    firecrawl: FirecrawlClient | None = None,
    browserbase: BrowserbaseClient | None = None,
) -> FetchResult:
    firecrawl = firecrawl or FirecrawlClient()
    browserbase = browserbase or BrowserbaseClient()

    if firecrawl.configured:
        try:
            data = await firecrawl.scrape(url)
            payload = data.get("data") or data
            markdown = payload.get("markdown") or ""
            html = payload.get("html") or ""
            metadata = payload.get("metadata") or {}
            title = metadata.get("title")
            if markdown or html:
                return FetchResult(
                    url=url,
                    markdown=markdown or _html_to_markdown(html),
                    html=html,
                    title=title,
                    source_engine="firecrawl",
                    metadata=metadata,
                )
        except FirecrawlError as exc:
            logger.warning("Firecrawl failed for %s: %s. Trying Browserbase.", url, exc)

    if browserbase.configured:
        try:
            html = await browserbase.fetch_html(url)
            soup = BeautifulSoup(html or "", "lxml")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else None
            return FetchResult(
                url=url,
                markdown=_html_to_markdown(html),
                html=html,
                title=title,
                source_engine="browserbase",
                metadata={},
            )
        except BrowserbaseError as exc:
            logger.error("Browserbase fallback failed for %s: %s", url, exc)
            raise

    raise RuntimeError(
        f"No working fetcher configured for {url}. Set FIRECRAWL_API_KEY or BROWSERBASE_API_KEY."
    )
