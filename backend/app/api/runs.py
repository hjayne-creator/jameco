"""Run management endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.models.db import Run, Source, StepResult, get_engine
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
    runs = session.exec(select(Run).order_by(Run.id.desc())).all()
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
    return {
        "id": run.id,
        "subject_url": run.subject_url,
        "n_competitors": run.n_competitors,
        "style_guide_id": run.style_guide_id,
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
    run.status = "pending"
    run.error = None
    run.updated_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    await start_run(run_id)
    return {"id": run_id, "status": "pending"}
