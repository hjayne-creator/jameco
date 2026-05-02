"""Admin endpoints for LLM pricing and usage/cost reporting."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.db import LLMPriceCard, LLMUsageEvent, Run, get_engine

router = APIRouter()


def get_session():
    with Session(get_engine()) as session:
        yield session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/pricing")
def list_price_cards(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = session.exec(
        select(LLMPriceCard).order_by(
            LLMPriceCard.provider, LLMPriceCard.model, LLMPriceCard.effective_from.desc()
        )
    ).all()
    return [
        {
            "id": r.id,
            "provider": r.provider,
            "model": r.model,
            "input_per_million_usd": r.input_per_million_usd,
            "output_per_million_usd": r.output_per_million_usd,
            "cached_input_per_million_usd": r.cached_input_per_million_usd,
            "reasoning_per_million_usd": r.reasoning_per_million_usd,
            "effective_from": _iso(r.effective_from),
            "effective_to": _iso(r.effective_to),
            "active": r.active,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.post("/pricing")
def create_or_update_price_card(
    payload: dict[str, Any], session: Session = Depends(get_session)
) -> dict[str, Any]:
    provider = str(payload.get("provider", "")).strip().lower()
    model = str(payload.get("model", "")).strip()
    if not provider or not model:
        raise HTTPException(400, "provider and model are required")

    card_id = payload.get("id")
    card: LLMPriceCard | None = None
    if card_id is not None:
        card = session.get(LLMPriceCard, int(card_id))
        if card is None:
            raise HTTPException(404, "Price card not found")
    else:
        card = LLMPriceCard(provider=provider, model=model)

    card.provider = provider
    card.model = model
    card.input_per_million_usd = float(payload.get("input_per_million_usd", card.input_per_million_usd))
    card.output_per_million_usd = float(payload.get("output_per_million_usd", card.output_per_million_usd))
    card.cached_input_per_million_usd = float(
        payload.get("cached_input_per_million_usd", card.cached_input_per_million_usd)
    )
    card.reasoning_per_million_usd = float(
        payload.get("reasoning_per_million_usd", card.reasoning_per_million_usd)
    )
    card.active = bool(payload.get("active", card.active))
    card.notes = payload.get("notes", card.notes)

    if "effective_from" in payload:
        card.effective_from = datetime.fromisoformat(str(payload["effective_from"]))
    elif card.id is None:
        card.effective_from = _utcnow()

    if "effective_to" in payload:
        effective_to = payload["effective_to"]
        card.effective_to = datetime.fromisoformat(str(effective_to)) if effective_to else None

    session.add(card)
    session.commit()
    session.refresh(card)
    return {
        "id": card.id,
        "provider": card.provider,
        "model": card.model,
        "active": card.active,
        "effective_from": _iso(card.effective_from),
        "effective_to": _iso(card.effective_to),
    }


@router.get("/usage/events")
def list_usage_events(
    run_id: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(LLMUsageEvent).order_by(LLMUsageEvent.id.desc()).limit(limit)
    if run_id is not None:
        stmt = stmt.where(LLMUsageEvent.run_id == run_id)
    if provider:
        stmt = stmt.where(LLMUsageEvent.provider == provider)
    if model:
        stmt = stmt.where(LLMUsageEvent.model == model)

    rows = session.exec(stmt).all()
    return [
        {
            "id": r.id,
            "created_at": _iso(r.created_at),
            "provider": r.provider,
            "model": r.model,
            "run_id": r.run_id,
            "step_no": r.step_no,
            "step_name": r.step_name,
            "request_kind": r.request_kind,
            "status": r.status,
            "attempt_number": r.attempt_number,
            "provider_request_id": r.provider_request_id,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cached_input_tokens": r.cached_input_tokens,
            "reasoning_tokens": r.reasoning_tokens,
            "total_tokens": r.total_tokens,
            "latency_ms": r.latency_ms,
            "total_cost_usd": r.total_cost_usd,
            "pricing_version": r.pricing_version,
            "error": r.error,
        }
        for r in rows
    ]


@router.get("/usage/summary/daily")
def summarize_usage_daily(
    days: int = Query(default=14, ge=1, le=365),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    if session.bind is None:
        raise HTTPException(500, "Database session not bound")
    dialect = session.bind.dialect.name
    if dialect == "sqlite":
        day_expr = func.date(LLMUsageEvent.created_at)
    else:
        day_expr = func.date_trunc("day", LLMUsageEvent.created_at)

    cutoff = _utcnow()
    cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    # Approximate N-day window starting midnight UTC.
    from datetime import timedelta

    cutoff = cutoff - timedelta(days=days - 1)

    stmt = (
        select(
            day_expr.label("day"),
            LLMUsageEvent.provider,
            LLMUsageEvent.model,
            func.count(LLMUsageEvent.id).label("events"),
            func.sum(LLMUsageEvent.input_tokens).label("input_tokens"),
            func.sum(LLMUsageEvent.output_tokens).label("output_tokens"),
            func.sum(LLMUsageEvent.total_tokens).label("total_tokens"),
            func.sum(LLMUsageEvent.total_cost_usd).label("total_cost_usd"),
        )
        .where(LLMUsageEvent.created_at >= cutoff)
        .group_by(day_expr, LLMUsageEvent.provider, LLMUsageEvent.model)
        .order_by(day_expr.desc(), LLMUsageEvent.provider, LLMUsageEvent.model)
    )
    rows = session.exec(stmt).all()
    return [
        {
            "day": str(r.day),
            "provider": r.provider,
            "model": r.model,
            "events": int(r.events or 0),
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "total_tokens": int(r.total_tokens or 0),
            "total_cost_usd": float(r.total_cost_usd or 0.0),
        }
        for r in rows
    ]


@router.get("/usage/summary/runs")
def summarize_usage_by_run(
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(
            LLMUsageEvent.run_id,
            Run.subject_url,
            func.count(LLMUsageEvent.id).label("events"),
            func.sum(LLMUsageEvent.total_tokens).label("total_tokens"),
            func.sum(LLMUsageEvent.total_cost_usd).label("total_cost_usd"),
            func.max(LLMUsageEvent.created_at).label("last_event_at"),
        )
        .join(Run, Run.id == LLMUsageEvent.run_id, isouter=True)
        .group_by(LLMUsageEvent.run_id, Run.subject_url)
        .order_by(func.sum(LLMUsageEvent.total_cost_usd).desc())
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    return [
        {
            "run_id": r.run_id,
            "subject_url": r.subject_url,
            "events": int(r.events or 0),
            "total_tokens": int(r.total_tokens or 0),
            "total_cost_usd": float(r.total_cost_usd or 0.0),
            "last_event_at": _iso(r.last_event_at),
        }
        for r in rows
    ]
