"""Provider-agnostic helpers used by step modules."""
from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel

from app.adapters import ClaudeClient, OpenAIClient
from app.workflow.prompts import PromptConfig, cfg, load_text

T = TypeVar("T", bound=BaseModel)

SYSTEM_BASE = load_text("system.md")


async def call_json(
    config: PromptConfig,
    *,
    system: str,
    user: str,
    schema: Type[T],
    temperature: float = 0.0,
    max_tokens: int = 6000,
) -> T:
    full_system = f"{SYSTEM_BASE}\n\n{system}".strip()
    if config.provider == "claude":
        client = ClaudeClient()
        if not client.configured:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        return await client.complete_json(
            model=config.model,
            system=full_system,
            user=user,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    client = OpenAIClient()
    if not client.configured:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return await client.complete_json(
        model=config.model,
        system=full_system,
        user=user,
        schema=schema,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def call_text(
    config: PromptConfig,
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> str:
    full_system = f"{SYSTEM_BASE}\n\n{system}".strip()
    if config.provider == "claude":
        client = ClaudeClient()
        if not client.configured:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        return await client.complete_text(
            model=config.model,
            system=full_system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    client = OpenAIClient()
    if not client.configured:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return await client.complete_text(
        model=config.model,
        system=full_system,
        user=user,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def role_cfg(role) -> PromptConfig:
    return cfg(role)
