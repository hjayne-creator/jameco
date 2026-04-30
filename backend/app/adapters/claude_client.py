"""Anthropic Claude wrapper with both text and JSON-typed completions."""
from __future__ import annotations

import json
import logging
from typing import Any, Type, TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ClaudeClientError(RuntimeError):
    pass


class ClaudeClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_settings().anthropic_api_key
        self._client: AsyncAnthropic | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _client_or_raise(self) -> AsyncAnthropic:
        if not self.configured:
            raise ClaudeClientError("ANTHROPIC_API_KEY is not configured")
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete_text(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        client = self._client_or_raise()
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                response = await client.messages.create(
                    model=model,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": user}],
                )
                parts = []
                for block in response.content:
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(text)
                return "\n".join(parts)
        raise ClaudeClientError("Claude text completion exhausted retries")

    async def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: Type[T],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> T:
        json_instruction = (
            "Respond ONLY with a JSON object that matches this JSON schema. "
            "Do not include prose, markdown fences, or commentary.\n\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}"
        )
        full_system = system + "\n\n" + json_instruction
        request_user = user
        token_budget = max_tokens
        cleaned = ""
        for attempt_idx in range(3):
            text = await self.complete_text(
                model=model,
                system=full_system,
                user=request_user,
                temperature=temperature,
                max_tokens=token_budget,
            )
            cleaned = _strip_json_fences(text)
            try:
                data = json.loads(cleaned)
                return schema.model_validate(data)
            except json.JSONDecodeError:
                logger.warning(
                    "Claude returned malformed JSON (attempt %s/3); retrying with tighter prompt",
                    attempt_idx + 1,
                )
                request_user = (
                    user
                    + "\n\nIMPORTANT: Your prior response was malformed/truncated. "
                    "Return a complete, valid JSON object only. Keep values concise."
                )
                token_budget = min(max(token_budget + 2000, int(token_budget * 1.5)), 12000)

        logger.warning("Claude malformed JSON persisted; attempting structured repair")
        data = await self._repair_json(
            model=model,
            malformed_json=cleaned,
            schema=schema,
            max_tokens=min(max(max_tokens * 2, 8000), 12000),
        )
        return schema.model_validate(data)

    async def _repair_json(
        self,
        *,
        model: str,
        malformed_json: str,
        schema: Type[T],
        max_tokens: int,
    ) -> Any:
        """Ask Claude to repair malformed JSON into schema-conformant JSON only."""
        repair_system = (
            "You are a JSON repair engine. "
            "Return ONLY a valid JSON object, with no markdown fences or commentary."
        )
        repair_user = (
            "Repair this malformed JSON into a valid JSON object matching the schema.\n\n"
            "JSON schema:\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}\n\n"
            "Malformed JSON:\n"
            f"{malformed_json}"
        )
        repaired = await self.complete_text(
            model=model,
            system=repair_system,
            user=repair_user,
            temperature=0.0,
            max_tokens=max_tokens,
        )
        cleaned_repaired = _strip_json_fences(repaired)
        try:
            return json.loads(cleaned_repaired)
        except json.JSONDecodeError as exc:
            raise ClaudeClientError(
                f"Claude returned non-JSON: {cleaned_repaired[:300]}"
            ) from exc


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
