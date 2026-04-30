"""OpenAI client wrapper that returns parsed JSON for our typed step calls."""
from __future__ import annotations

import json
import logging
from typing import Any, Type, TypeVar

from openai import AsyncOpenAI, BadRequestError
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


class OpenAIClientError(RuntimeError):
    pass


class OpenAIClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_settings().openai_api_key
        self._client: AsyncOpenAI | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _client_or_raise(self) -> AsyncOpenAI:
        if not self.configured:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    @staticmethod
    def _is_unsupported_response_format_error(exc: BadRequestError) -> bool:
        msg = str(exc).lower()
        return "response_format" in msg and (
            "unsupported" in msg or "not supported" in msg
        )

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
                request: dict[str, Any] = {
                    "model": model,
                    "max_completion_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
                response = await client.chat.completions.create(**request)
                return response.choices[0].message.content or ""
        raise OpenAIClientError("OpenAI text completion exhausted retries")

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
        """Force JSON output and parse against a Pydantic model.

        Uses response_format=json_object plus an explicit schema instruction.
        """
        client = self._client_or_raise()
        json_instruction = (
            "Respond ONLY with a JSON object that matches this JSON schema. "
            "Do not include prose, markdown fences, or commentary.\n\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}"
        )
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                request: dict[str, Any] = {
                    "model": model,
                    "max_completion_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system + "\n\n" + json_instruction},
                        {"role": "user", "content": user},
                    ],
                }
                try:
                    response = await client.chat.completions.create(**request)
                except BadRequestError as exc:
                    # Some model/endpoint combos reject response_format.
                    if self._is_unsupported_response_format_error(exc):
                        request.pop("response_format", None)
                    else:
                        raise
                    try:
                        response = await client.chat.completions.create(**request)
                    except BadRequestError as exc2:
                        if self._is_unsupported_response_format_error(exc2):
                            request.pop("response_format", None)
                            response = await client.chat.completions.create(**request)
                        else:
                            raise
                raw = response.choices[0].message.content or "{}"
                try:
                    data: Any = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise OpenAIClientError(f"OpenAI returned non-JSON: {raw[:300]}") from exc
                return schema.model_validate(data)
        raise OpenAIClientError("OpenAI JSON completion exhausted retries")
