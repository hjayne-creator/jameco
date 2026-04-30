"""Prompt registry. Centralizes per-step model selection + system prompts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.config import get_settings

Role = Literal["extraction", "reasoning", "writing"]


@dataclass
class PromptConfig:
    role: Role
    provider: Literal["openai", "claude"]
    model: str


def _settings_model(role: Role) -> str:
    s = get_settings()
    if role == "extraction":
        return s.llm_extraction_model
    if role == "reasoning":
        return s.llm_reasoning_model
    return s.llm_writing_model


def _provider_for(role: Role) -> Literal["openai", "claude"]:
    model = _settings_model(role)
    return "claude" if model.lower().startswith("claude") else "openai"


def cfg(role: Role) -> PromptConfig:
    return PromptConfig(role=role, provider=_provider_for(role), model=_settings_model(role))


def load_text(name: str) -> str:
    here = Path(__file__).parent
    path = here / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
