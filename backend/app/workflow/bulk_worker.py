"""FIFO queue: one batch at a time, serial URLs within each batch."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.db import Batch, Run, get_engine
from app.models.schemas import BulkOptions
from app.workflow.bulk_orchestrator import execute_bulk_pipeline

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[int] = asyncio.Queue()
_worker_task: asyncio.Task[None] | None = None

_RUN_TERMINAL = frozenset({"done", "skipped", "failed"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_batch(batch_id: int) -> None:
    _queue.put_nowait(batch_id)


def _summarize_run_failures(runs: list[Run]) -> str:
    failed = [r for r in runs if r.status == "failed"]
    if not failed:
        return ""
    parts = [f"{len(failed)} of {len(runs)} URL run(s) failed."]
    for r in failed[:3]:
        msg = ((r.error or "unknown").replace("\n", " "))[:220]
        parts.append(f"#{r.id}: {msg}")
    if len(failed) > 3:
        parts.append(f"(+{len(failed) - 3} more)")
    return " ".join(parts)


def finalize_batch_record(batch_id: int) -> None:
    """Set batch.status and batch.error from child runs (call after processing stops)."""
    with Session(get_engine()) as session:
        batch = session.get(Batch, batch_id)
        if batch is None:
            return
        runs = list(session.exec(select(Run).where(Run.batch_id == batch_id)).all())
        if not runs:
            batch.status = "done"
            batch.error = None
            batch.updated_at = _now()
            session.add(batch)
            session.commit()
            return

        non_terminal = [r for r in runs if r.status not in _RUN_TERMINAL]
        n_failed = sum(1 for r in runs if r.status == "failed")

        if non_terminal:
            batch.status = "failed"
            statuses = ", ".join(sorted({r.status for r in non_terminal}))[:160]
            batch.error = (
                f"Batch ended with {len(non_terminal)} run(s) not in a final state ({statuses}). "
                "This usually means the worker stopped before every URL was processed."
            )
        elif n_failed > 0:
            batch.status = "failed"
            batch.error = _summarize_run_failures(runs)
        else:
            batch.status = "done"
            batch.error = None

        batch.updated_at = _now()
        session.add(batch)
        session.commit()


def maybe_autofinalize_stuck_batch(batch_id: int) -> None:
    """If batch is still `running` but every child run is terminal, apply finalize (fixes stuck UI)."""
    with Session(get_engine()) as session:
        batch = session.get(Batch, batch_id)
        if batch is None or batch.status != "running":
            return
        runs = list(session.exec(select(Run).where(Run.batch_id == batch_id)).all())
    if runs and all(r.status in _RUN_TERMINAL for r in runs):
        finalize_batch_record(batch_id)


def repair_stuck_running_batches() -> None:
    """On cold process start: recompute any batch still marked `running` (worker task did not survive restart)."""
    with Session(get_engine()) as session:
        stuck = session.exec(select(Batch).where(Batch.status == "running")).all()
        ids = [b.id for b in stuck if b.id is not None]
    for bid in ids:
        finalize_batch_record(bid)


def _mark_run_failed_from_worker_crash(run_id: int, exc: BaseException) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        if run.status in _RUN_TERMINAL:
            return
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        session.add(run)
        session.commit()


async def start_bulk_worker() -> None:
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker_loop(), name="bulk-worker")


async def _worker_loop() -> None:
    while True:
        batch_id = await _queue.get()
        try:
            await _process_batch(batch_id)
        except Exception:
            logger.exception("Unhandled error processing batch %s", batch_id)
        finally:
            _queue.task_done()


async def _process_batch(batch_id: int) -> None:
    run_ids: list[int] = []
    try:
        with Session(get_engine()) as session:
            batch = session.get(Batch, batch_id)
            if batch is None:
                return
            snapshot = dict(batch.options_snapshot or {})
            batch.status = "running"
            batch.error = None
            batch.updated_at = _now()
            session.add(batch)
            session.commit()
            runs = session.exec(
                select(Run).where(Run.batch_id == batch_id).order_by(Run.batch_index)
            ).all()
            run_ids = [r.id for r in runs if r.id is not None]

        options = BulkOptions.model_validate(snapshot)

        for rid in run_ids:
            try:
                await execute_bulk_pipeline(rid, options)
            except Exception as exc:
                logger.exception("Unhandled error in bulk pipeline for run %s (batch %s)", rid, batch_id)
                _mark_run_failed_from_worker_crash(rid, exc)
    finally:
        try:
            finalize_batch_record(batch_id)
        except Exception:
            logger.exception("finalize_batch_record failed for batch %s", batch_id)
