"""Serial PDP pipeline for bulk runs: no interactive checkpoints."""
from __future__ import annotations

import logging

from sqlmodel import Session

from app.events import bus
from app.models.db import Run, get_engine
from app.models.schemas import BulkOptions
from app.workflow.bulk_policy import (
    apply_competitor_auto_policy,
    identity_effectively_empty,
    identity_is_ambiguous,
)
from app.workflow.orchestrator import (
    _execute_step,
    _load_state,
    _load_step_outputs,
    _save_run,
    _serialize,
    _upsert_step_result,
)
from app.workflow.pipeline_lock import get_pipeline_lock
from app.workflow.registry import STEPS

logger = logging.getLogger(__name__)


def _mark_skip(run_id: int, reason: str, current_step: int) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        run.status = "skipped"
        run.terminal_reason = reason
        run.current_step = current_step
        run.error = None
        _save_run(session, run)


def _mark_failed(run_id: int, message: str, current_step: int) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        run.status = "failed"
        run.error = message
        run.terminal_reason = None
        run.current_step = current_step
        _save_run(session, run)


def _mark_done(run_id: int) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        run.status = "done"
        run.current_step = STEPS[-1].step_no
        run.error = None
        run.terminal_reason = None
        _save_run(session, run)


async def execute_bulk_pipeline(run_id: int, options: BulkOptions) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")
        if run.batch_id is None:
            raise ValueError("Bulk pipeline requires run.batch_id")
        run.status = "running"
        run.error = None
        run.terminal_reason = None
        _save_run(session, run)
        state = _load_state(session, run)
        state.gap_min_distinct_domains = options.min_distinct_competitor_domains
        state.bulk_auto_gap_finalize = True
        completed = set(_load_step_outputs(session, run_id).keys())

    await bus.publish(run_id, "run.started", {"run_id": run_id, "bulk": True})

    for step_def in STEPS:
        if step_def.step_no in completed:
            await bus.publish(
                run_id,
                "step.skipped",
                {"step_no": step_def.step_no, "name": step_def.name, "label": step_def.label},
            )
            continue

        try:
            lock = get_pipeline_lock()
            async with lock:
                await _execute_step(run_id, state, step_def)
        except Exception as exc:
            logger.exception("Bulk step %s failed for run %s", step_def.step_no, run_id)
            _mark_failed(run_id, f"{type(exc).__name__}: {exc}", step_def.step_no)
            await bus.publish(
                run_id,
                "run.bulk_failed",
                {
                    "run_id": run_id,
                    "step_no": step_def.step_no,
                    "name": step_def.name,
                    "label": step_def.label,
                    "message": str(exc),
                },
            )
            return

        completed.add(step_def.step_no)

        if step_def.checkpoint == "identity":
            assert state.identity_lock is not None
            if identity_is_ambiguous(state.identity_lock):
                _mark_skip(run_id, "skipped_ambiguous_identity", step_def.step_no)
                await bus.publish(
                    run_id,
                    "run.bulk_skipped",
                    {"run_id": run_id, "reason": "skipped_ambiguous_identity", "step_no": step_def.step_no},
                )
                return
            if identity_effectively_empty(state.identity_lock):
                _mark_skip(run_id, "skipped_empty_identity", step_def.step_no)
                await bus.publish(
                    run_id,
                    "run.bulk_skipped",
                    {"run_id": run_id, "reason": "skipped_empty_identity", "step_no": step_def.step_no},
                )
                return

        if step_def.checkpoint == "competitors":
            assert state.competitor_list is not None
            apply_competitor_auto_policy(state.competitor_list, options)
            payload = _serialize(state.competitor_list)
            with Session(get_engine()) as session:
                _upsert_step_result(
                    session,
                    run_id=run_id,
                    step_no=4,
                    step_name="competitor_discovery",
                    status="completed",
                    output_payload=payload,
                )
            if state.competitor_list.accepted_count == 0:
                _mark_skip(run_id, "skipped_no_competitors", step_def.step_no)
                await bus.publish(
                    run_id,
                    "run.bulk_skipped",
                    {"run_id": run_id, "reason": "skipped_no_competitors", "step_no": step_def.step_no},
                )
                return

    _mark_done(run_id)
    await bus.publish(run_id, "run.completed", {"run_id": run_id, "bulk": True})
