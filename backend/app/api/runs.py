"""Run management endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.models.db import LLMUsageEvent, Run, Source, StepResult, get_engine
from app.models.schemas import CreateRunRequest
from app.workflow.orchestrator import start_run

router = APIRouter()


def get_session():
    with Session(get_engine()) as session:
        yield session


@router.post("")
async def create_run(payload: CreateRunRequest, session: Session = Depends(get_session)) -> dict:
    run = Run(
        subject_url=str(payload.subject_url),
        n_competitors=payload.n_competitors,
        style_guide_id=payload.style_guide_id,
        status="pending",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    assert run.id is not None
    await start_run(run.id)
    return {"id": run.id, "status": run.status}


@router.get("")
def list_runs(session: Session = Depends(get_session)) -> list[dict]:
    runs = session.exec(
        select(Run).where(Run.batch_id.is_(None)).order_by(desc(Run.id))
    ).all()
    run_ids = [r.id for r in runs if r.id is not None]
    usage_by_run: dict[int, tuple[int, float]] = {}
    if run_ids:
        usage_rows = session.exec(
            select(
                LLMUsageEvent.run_id,
                func.sum(LLMUsageEvent.total_tokens).label("total_tokens"),
                func.sum(LLMUsageEvent.total_cost_usd).label("total_cost_usd"),
            )
            .where(LLMUsageEvent.run_id.in_(run_ids))
            .group_by(LLMUsageEvent.run_id)
        ).all()
        usage_by_run = {
            int(row.run_id): (int(row.total_tokens or 0), float(row.total_cost_usd or 0.0))
            for row in usage_rows
            if row.run_id is not None
        }
    return [
        {
            "id": r.id,
            "subject_url": r.subject_url,
            "n_competitors": r.n_competitors,
            "status": r.status,
            "current_step": r.current_step,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
            "error": r.error,
            "llm_total_tokens": usage_by_run.get(r.id or -1, (0, 0.0))[0],
            "llm_total_cost_usd": usage_by_run.get(r.id or -1, (0, 0.0))[1],
        }
        for r in runs
    ]


def _serialize_run(session: Session, run: Run) -> dict[str, Any]:
    steps = session.exec(
        select(StepResult).where(StepResult.run_id == run.id).order_by(StepResult.step_no)
    ).all()
    sources = session.exec(
        select(Source).where(Source.run_id == run.id).order_by(Source.id)
    ).all()
    usage_rows = session.exec(
        select(
            LLMUsageEvent.step_no,
            LLMUsageEvent.step_name,
            LLMUsageEvent.provider,
            LLMUsageEvent.model,
            func.count(LLMUsageEvent.id).label("events"),
            func.sum(LLMUsageEvent.total_tokens).label("total_tokens"),
            func.sum(LLMUsageEvent.input_tokens).label("input_tokens"),
            func.sum(LLMUsageEvent.output_tokens).label("output_tokens"),
            func.sum(LLMUsageEvent.total_cost_usd).label("total_cost_usd"),
        )
        .where(LLMUsageEvent.run_id == run.id)
        .group_by(
            LLMUsageEvent.step_no,
            LLMUsageEvent.step_name,
            LLMUsageEvent.provider,
            LLMUsageEvent.model,
        )
        .order_by(LLMUsageEvent.step_no, LLMUsageEvent.provider, LLMUsageEvent.model)
    ).all()
    usage_overview = session.exec(
        select(
            func.count(LLMUsageEvent.id).label("events"),
            func.sum(LLMUsageEvent.total_tokens).label("total_tokens"),
            func.sum(LLMUsageEvent.total_cost_usd).label("total_cost_usd"),
        )
        .where(LLMUsageEvent.run_id == run.id)
    ).one()
    return {
        "id": run.id,
        "subject_url": run.subject_url,
        "n_competitors": run.n_competitors,
        "style_guide_id": run.style_guide_id,
        "batch_id": run.batch_id,
        "terminal_reason": run.terminal_reason,
        "status": run.status,
        "current_step": run.current_step,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "steps": [
            {
                "id": s.id,
                "step_no": s.step_no,
                "step_name": s.step_name,
                "status": s.status,
                "output": s.output_json,
                "duration_ms": s.duration_ms,
                "model_used": s.model_used,
                "error": s.error,
                "updated_at": s.updated_at.isoformat(),
            }
            for s in steps
        ],
        "sources": [
            {
                "id": s.id,
                "url": s.url,
                "kind": s.kind,
                "title": s.title,
                "classification": s.classification,
                "notes": s.notes,
                "fetched_at": s.fetched_at.isoformat(),
            }
            for s in sources
        ],
        "llm_usage": {
            "events": int(usage_overview.events or 0),
            "total_tokens": int(usage_overview.total_tokens or 0),
            "total_cost_usd": float(usage_overview.total_cost_usd or 0.0),
            "by_step": [
                {
                    "step_no": row.step_no,
                    "step_name": row.step_name,
                    "provider": row.provider,
                    "model": row.model,
                    "events": int(row.events or 0),
                    "input_tokens": int(row.input_tokens or 0),
                    "output_tokens": int(row.output_tokens or 0),
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
                }
                for row in usage_rows
            ],
        },
    }


@router.get("/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return _serialize_run(session, run)


@router.post("/{run_id}/restart")
async def restart_run(run_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    if run.batch_id is not None:
        raise HTTPException(400, "Bulk batch runs cannot be restarted from this endpoint")
    run.status = "pending"
    run.error = None
    run.updated_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    await start_run(run_id)
    return {"id": run_id, "status": "pending"}
