"""Drives the 10-step PDP pipeline with pause-at-checkpoint semantics."""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from pydantic import BaseModel
from sqlmodel import Session, select

from app.events import bus
from app.models.db import Run, StepResult, StyleGuide, get_engine
from app.models.schemas import (
    CompetitorExtracts,
    CompetitorList,
    FinalCopy,
    GapValidation,
    HtmlCopy,
    IdentityLock,
    ManufacturerVerification,
    SubjectExtract,
)
from app.observability.llm_usage import llm_call_context
from app.workflow.pipeline_lock import get_pipeline_lock
from app.workflow.registry import CHECKPOINT_AFTER_STEP, STEPS, StepDefinition, step_by_checkpoint
from app.workflow.state import RunState
from app.workflow.steps import (
    step1_extract,
    step2_identity,
    step3_manufacturer,
    step4_competitor_discovery,
    step5_competitor_extract,
    step6_gap_validation,
    step7_final_copy,
    step8_html,
    step9_jsonld,
    step10_assemble,
)

logger = logging.getLogger(__name__)

_running_tasks: dict[int, asyncio.Task] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- DB helpers ---------------------------------------------------------------


def _save_run(session: Session, run: Run) -> None:
    run.updated_at = _now()
    session.add(run)
    session.commit()


def _upsert_step_result(
    session: Session,
    *,
    run_id: int,
    step_no: int,
    step_name: str,
    status: str,
    input_payload: Optional[dict] = None,
    output_payload: Optional[dict] = None,
    duration_ms: Optional[int] = None,
    model_used: Optional[str] = None,
    error: Optional[str] = None,
) -> StepResult:
    existing = session.exec(
        select(StepResult).where(StepResult.run_id == run_id, StepResult.step_no == step_no)
    ).first()
    if existing is None:
        existing = StepResult(run_id=run_id, step_no=step_no, step_name=step_name)
    existing.status = status
    if input_payload is not None:
        existing.input_json = input_payload
    if output_payload is not None:
        existing.output_json = output_payload
    if duration_ms is not None:
        existing.duration_ms = duration_ms
    if model_used is not None:
        existing.model_used = model_used
    if error is not None:
        existing.error = error
    existing.updated_at = _now()
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def _load_step_outputs(session: Session, run_id: int) -> dict[int, dict[str, Any]]:
    rows = session.exec(
        select(StepResult).where(StepResult.run_id == run_id, StepResult.status == "completed")
    ).all()
    return {r.step_no: (r.output_json or {}) for r in rows}


def _load_state(session: Session, run: Run) -> RunState:
    style_text = ""
    if run.style_guide_id:
        sg = session.get(StyleGuide, run.style_guide_id)
        if sg:
            style_text = sg.text

    state = RunState(
        run_id=run.id or 0,
        subject_url=run.subject_url,
        n_competitors=run.n_competitors,
        style_guide_text=style_text,
    )

    outputs = _load_step_outputs(session, run.id or 0)
    if 1 in outputs:
        state.subject_extract = SubjectExtract.model_validate(outputs[1])
    if 2 in outputs:
        state.identity_lock = IdentityLock.model_validate(outputs[2])
    if 3 in outputs:
        state.manufacturer = ManufacturerVerification.model_validate(outputs[3])
    if 4 in outputs:
        state.competitor_list = CompetitorList.model_validate(outputs[4])
    if 5 in outputs:
        state.competitor_extracts = CompetitorExtracts.model_validate(outputs[5])
    if 6 in outputs:
        state.gap_validation = GapValidation.model_validate(outputs[6])
    if 7 in outputs:
        state.final_copy = FinalCopy.model_validate(outputs[7])
    if 8 in outputs:
        state.html_copy = HtmlCopy.model_validate(outputs[8])
    if 9 in outputs:
        state.json_ld = outputs[9]
    return state


# --- Step dispatch ------------------------------------------------------------


_STEP_FUNCS: dict[int, Callable] = {
    1: step1_extract.run,
    2: step2_identity.run,
    3: step3_manufacturer.run,
    4: step4_competitor_discovery.run,
    5: step5_competitor_extract.run,
    6: step6_gap_validation.run,
    7: step7_final_copy.run,
    8: step8_html.run,
    9: step9_jsonld.run,
    10: step10_assemble.run,
}


def _serialize(payload: Any) -> dict:
    if payload is None:
        return {}
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


# --- Public entrypoints -------------------------------------------------------


async def start_run(run_id: int) -> None:
    """Schedule a background task to run / resume the orchestrator."""
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is not None and run.batch_id is not None:
            return
    if run_id in _running_tasks and not _running_tasks[run_id].done():
        return
    task = asyncio.create_task(_run_loop(run_id), name=f"run-{run_id}")
    _running_tasks[run_id] = task


async def _run_loop(run_id: int) -> None:
    try:
        await _execute_run(run_id)
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        with Session(get_engine()) as session:
            run = session.get(Run, run_id)
            if run:
                run.status = "error"
                run.error = f"{type(exc).__name__}: {exc}"
                _save_run(session, run)
        await bus.publish(run_id, "run.error", {"message": str(exc), "trace": traceback.format_exc()})


async def _execute_run(run_id: int) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")
        run.status = "running"
        run.error = None
        _save_run(session, run)

        await bus.publish(run_id, "run.started", {"run_id": run_id})

        state = _load_state(session, run)
        completed = set(_load_step_outputs(session, run_id).keys())

    for step_def in STEPS:
        if step_def.step_no in completed:
            await bus.publish(
                run_id,
                "step.skipped",
                {
                    "step_no": step_def.step_no,
                    "name": step_def.name,
                    "label": step_def.label,
                },
            )
            continue

        lock = get_pipeline_lock()
        async with lock:
            await _execute_step(run_id, state, step_def)

        if step_def.checkpoint:
            with Session(get_engine()) as session:
                run = session.get(Run, run_id)
                assert run is not None
                run.status = f"awaiting_checkpoint:{step_def.checkpoint}"
                run.current_step = step_def.step_no
                _save_run(session, run)
            await bus.publish(
                run_id,
                "checkpoint.pause",
                {
                    "step_no": step_def.step_no,
                    "name": step_def.checkpoint,
                    "label": step_def.label,
                },
            )
            return  # Wait for resume

    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        assert run is not None
        run.status = "done"
        run.current_step = STEPS[-1].step_no
        _save_run(session, run)
    await bus.publish(run_id, "run.completed", {"run_id": run_id})


async def _execute_step(run_id: int, state: RunState, step_def: StepDefinition) -> None:
    await bus.publish(
        run_id,
        "step.started",
        {"step_no": step_def.step_no, "name": step_def.name, "label": step_def.label},
    )
    started = time.monotonic()
    func = _STEP_FUNCS[step_def.step_no]

    with Session(get_engine()) as session:
        _upsert_step_result(
            session,
            run_id=run_id,
            step_no=step_def.step_no,
            step_name=step_def.name,
            status="running",
        )
        run = session.get(Run, run_id)
        if run:
            run.current_step = step_def.step_no
            _save_run(session, run)

    try:
        with llm_call_context(run_id=run_id, step_no=step_def.step_no, step_name=step_def.name):
            result = await func(state, run_id=run_id)
        duration_ms = int((time.monotonic() - started) * 1000)
        output_payload = _serialize(result)
        _apply_step_output(state, step_def.step_no, result)

        with Session(get_engine()) as session:
            _upsert_step_result(
                session,
                run_id=run_id,
                step_no=step_def.step_no,
                step_name=step_def.name,
                status="completed",
                output_payload=output_payload,
                duration_ms=duration_ms,
            )
        await bus.publish(
            run_id,
            "step.completed",
            {
                "step_no": step_def.step_no,
                "name": step_def.name,
                "label": step_def.label,
                "duration_ms": duration_ms,
            },
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.exception("Step %s failed for run %s", step_def.step_no, run_id)
        with Session(get_engine()) as session:
            _upsert_step_result(
                session,
                run_id=run_id,
                step_no=step_def.step_no,
                step_name=step_def.name,
                status="error",
                duration_ms=duration_ms,
                error=f"{type(exc).__name__}: {exc}",
            )
        await bus.publish(
            run_id,
            "step.error",
            {
                "step_no": step_def.step_no,
                "name": step_def.name,
                "label": step_def.label,
                "message": str(exc),
            },
        )
        raise


def _apply_step_output(state: RunState, step_no: int, result: Any) -> None:
    if step_no == 1 and isinstance(result, SubjectExtract):
        state.subject_extract = result
    elif step_no == 2 and isinstance(result, IdentityLock):
        state.identity_lock = result
    elif step_no == 3 and isinstance(result, ManufacturerVerification):
        state.manufacturer = result
    elif step_no == 4 and isinstance(result, CompetitorList):
        state.competitor_list = result
    elif step_no == 5 and isinstance(result, CompetitorExtracts):
        state.competitor_extracts = result
    elif step_no == 6 and isinstance(result, GapValidation):
        state.gap_validation = result
    elif step_no == 7 and isinstance(result, FinalCopy):
        state.final_copy = result
    elif step_no == 8 and isinstance(result, HtmlCopy):
        state.html_copy = result
    elif step_no == 9 and isinstance(result, dict):
        state.json_ld = result


# --- Checkpoint resume --------------------------------------------------------


CHECKPOINT_TO_STEP: dict[str, int] = {v: k for k, v in CHECKPOINT_AFTER_STEP.items()}


async def approve_checkpoint(run_id: int, checkpoint_name: str, edited_payload: dict) -> None:
    """Persist the user's (possibly edited) checkpoint output and resume the run."""
    if checkpoint_name not in CHECKPOINT_TO_STEP:
        raise ValueError(f"Unknown checkpoint: {checkpoint_name}")
    step_no = CHECKPOINT_TO_STEP[checkpoint_name]

    schema_cls = {
        2: IdentityLock,
        4: CompetitorList,
        6: GapValidation,
        7: FinalCopy,
    }[step_no]
    validated = schema_cls.model_validate(edited_payload)

    with Session(get_engine()) as session:
        existing = session.exec(
            select(StepResult).where(StepResult.run_id == run_id, StepResult.step_no == step_no)
        ).first()
        if existing is None:
            raise ValueError(f"No step result to update for checkpoint {checkpoint_name}")
        existing.output_json = validated.model_dump(mode="json")
        existing.status = "completed"
        existing.updated_at = _now()
        session.add(existing)

        run = session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")
        run.status = "running"
        _save_run(session, run)

    ck_step = step_by_checkpoint(checkpoint_name)
    await bus.publish(
        run_id,
        "checkpoint.approved",
        {"name": checkpoint_name, "step_no": step_no, "label": ck_step.label},
    )

    await start_run(run_id)
