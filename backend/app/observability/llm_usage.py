from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.db import LLMPriceCard, LLMUsageEvent, get_engine

logger = logging.getLogger(__name__)


@dataclass
class LLMCallContext:
    run_id: int | None = None
    step_no: int | None = None
    step_name: str | None = None


_CONTEXT: ContextVar[LLMCallContext] = ContextVar("llm_call_context", default=LLMCallContext())


def _now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def llm_call_context(*, run_id: int, step_no: int, step_name: str):
    token: Token[LLMCallContext] = _CONTEXT.set(
        LLMCallContext(run_id=run_id, step_no=step_no, step_name=step_name)
    )
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def get_llm_call_context() -> LLMCallContext:
    return _CONTEXT.get()


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def extract_openai_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    return {
        "input_tokens": _as_int(getattr(usage, "prompt_tokens", 0)),
        "output_tokens": _as_int(getattr(usage, "completion_tokens", 0)),
        "total_tokens": _as_int(getattr(usage, "total_tokens", 0)),
        "cached_input_tokens": _as_int(getattr(prompt_details, "cached_tokens", 0)),
        "reasoning_tokens": _as_int(getattr(completion_details, "reasoning_tokens", 0)),
    }


def extract_anthropic_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return {
        "input_tokens": _as_int(getattr(usage, "input_tokens", 0)),
        "output_tokens": _as_int(getattr(usage, "output_tokens", 0)),
        "cached_input_tokens": _as_int(getattr(usage, "cache_read_input_tokens", 0)),
        "reasoning_tokens": _as_int(getattr(usage, "thinking_tokens", 0)),
        "total_tokens": _as_int(
            _as_int(getattr(usage, "input_tokens", 0))
            + _as_int(getattr(usage, "output_tokens", 0))
        ),
    }


def _resolve_price_card(*, provider: str, model: str, now: datetime) -> LLMPriceCard | None:
    with Session(get_engine()) as session:
        return session.exec(
            select(LLMPriceCard)
            .where(
                LLMPriceCard.provider == provider,
                LLMPriceCard.model == model,
                LLMPriceCard.active.is_(True),
                LLMPriceCard.effective_from <= now,
            )
            .where((LLMPriceCard.effective_to.is_(None)) | (LLMPriceCard.effective_to > now))
            .order_by(LLMPriceCard.effective_from.desc())
        ).first()


def _per_million_to_cost(token_count: int, per_million_usd: float) -> float:
    if token_count <= 0 or per_million_usd <= 0:
        return 0.0
    return (token_count / 1_000_000.0) * per_million_usd


def log_llm_usage_event(
    *,
    provider: str,
    model: str,
    request_kind: str,
    status: str,
    attempt_number: int,
    started_at_ms: int,
    response: Any = None,
    error: str | None = None,
) -> None:
    try:
        now = _now()
        context = get_llm_call_context()
        usage_by_provider = (
            extract_openai_usage(response) if provider == "openai" else extract_anthropic_usage(response)
        )
        input_tokens = usage_by_provider.get("input_tokens", 0)
        output_tokens = usage_by_provider.get("output_tokens", 0)
        cached_input_tokens = usage_by_provider.get("cached_input_tokens", 0)
        reasoning_tokens = usage_by_provider.get("reasoning_tokens", 0)
        total_tokens = usage_by_provider.get("total_tokens", input_tokens + output_tokens)

        price_card = _resolve_price_card(provider=provider, model=model, now=now)
        input_cost = 0.0
        output_cost = 0.0
        cached_input_cost = 0.0
        reasoning_cost = 0.0
        pricing_version = "none"
        if price_card is not None:
            input_cost = _per_million_to_cost(input_tokens, price_card.input_per_million_usd)
            output_cost = _per_million_to_cost(output_tokens, price_card.output_per_million_usd)
            cached_input_cost = _per_million_to_cost(
                cached_input_tokens, price_card.cached_input_per_million_usd
            )
            reasoning_cost = _per_million_to_cost(
                reasoning_tokens, price_card.reasoning_per_million_usd
            )
            pricing_version = f"price_card:{price_card.id}"

        total_cost = input_cost + output_cost + cached_input_cost + reasoning_cost
        provider_request_id = getattr(response, "id", None)
        latency_ms = int(time.monotonic() * 1000) - started_at_ms

        with Session(get_engine()) as session:
            session.add(
                LLMUsageEvent(
                    provider=provider,
                    model=model,
                    run_id=context.run_id,
                    step_no=context.step_no,
                    step_name=context.step_name,
                    request_kind=request_kind,
                    status=status,
                    attempt_number=attempt_number,
                    provider_request_id=provider_request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_input_tokens,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    input_cost_usd=input_cost,
                    output_cost_usd=output_cost,
                    cached_input_cost_usd=cached_input_cost,
                    reasoning_cost_usd=reasoning_cost,
                    total_cost_usd=total_cost,
                    pricing_version=pricing_version,
                    error=error,
                    created_at=now,
                )
            )
            session.commit()
    except Exception:
        logger.exception("Failed to persist LLM usage event")
