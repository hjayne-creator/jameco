"""Thin async wrapper around the Firecrawl /v1/scrape endpoint.

We use the REST API directly rather than the SDK because we only need the
markdown + minimal metadata path and we want a uniform httpx error surface.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


class FirecrawlError(RuntimeError):
    pass


class FirecrawlClient:
    BASE_URL = "https://api.firecrawl.dev/v1"

    def __init__(self, api_key: str | None = None, timeout: float = 60.0) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.firecrawl_api_key
        self.wait_for_ms = settings.firecrawl_wait_for_ms
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def scrape(self, url: str, formats: list[str] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise FirecrawlError("FIRECRAWL_API_KEY is not configured")

        payload: dict[str, Any] = {
            "url": url,
            "formats": formats or ["markdown", "html"],
            "onlyMainContent": True,
        }
        if self.wait_for_ms is not None:
            payload["waitFor"] = self.wait_for_ms
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.BASE_URL}/scrape",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code >= 400:
                        raise FirecrawlError(
                            f"Firecrawl scrape failed for {url}: {response.status_code} {response.text[:300]}"
                        )
                    return response.json()
        raise FirecrawlError(f"Firecrawl scrape exhausted retries for {url}")
