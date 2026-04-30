"""Browserbase fallback fetcher.

Browserbase exposes Sessions + a CDP endpoint, but the simplest reliable
operation for our use case is "create a session, navigate, return HTML".
We do that via a session + the Sessions Debug endpoint.

For projects that prefer Playwright over CDP, swap in their SDK; the public
contract here is just `fetch_html(url) -> str`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class BrowserbaseError(RuntimeError):
    pass


class BrowserbaseClient:
    SESSIONS_URL = "https://api.browserbase.com/v1/sessions"

    def __init__(
        self,
        api_key: str | None = None,
        project_id: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.browserbase_api_key
        self.project_id = project_id or settings.browserbase_project_id
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.project_id)

    async def fetch_html(self, url: str) -> str:
        if not self.configured:
            raise BrowserbaseError("BROWSERBASE_API_KEY / BROWSERBASE_PROJECT_ID not configured")

        headers = {
            "X-BB-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            create = await client.post(
                self.SESSIONS_URL,
                json={"projectId": self.project_id},
                headers=headers,
            )
            if create.status_code >= 400:
                raise BrowserbaseError(
                    f"Browserbase session create failed: {create.status_code} {create.text[:300]}"
                )
            session = create.json()
            session_id = session.get("id") or session.get("sessionId")
            connect_url = session.get("connectUrl") or session.get("wsEndpoint")
            if not session_id:
                raise BrowserbaseError(f"Browserbase response missing session id: {session}")

            try:
                content_payload: dict[str, Any] = {"url": url}
                fetch = await client.post(
                    f"{self.SESSIONS_URL}/{session_id}/fetch",
                    json=content_payload,
                    headers=headers,
                )
                if fetch.status_code == 404:
                    raise BrowserbaseError(
                        "Browserbase /fetch endpoint not available for this account; "
                        "configure a CDP/Playwright fetcher instead."
                    )
                if fetch.status_code >= 400:
                    raise BrowserbaseError(
                        f"Browserbase fetch failed for {url}: {fetch.status_code} {fetch.text[:300]}"
                    )
                data = fetch.json()
                return data.get("html") or data.get("content") or ""
            finally:
                await asyncio.shield(
                    client.delete(f"{self.SESSIONS_URL}/{session_id}", headers=headers)
                )
