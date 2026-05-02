"""Bulk batch CRUD, CSV export."""
from __future__ import annotations

import csv
import io
import json
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import desc
from sqlmodel import Session, select

from app.config import get_settings
from app.models.db import Batch, Run, Source, StepResult, get_engine
from app.models.schemas import CreateBatchRequest
from app.workflow.registry import STEPS
from app.workflow.bulk_worker import (
    enqueue_batch,
    finalize_batch_record,
    maybe_autofinalize_stuck_batch,
)
from app.workflow.wysiwyg_export import final_copy_dict_to_wysiwyg_markdown

router = APIRouter()

_STEP_NAMES = {s.step_no: s.name for s in STEPS}
_REPORT_STEP_NOS = (7, 8, 9, 10)


def get_session():
    with Session(get_engine()) as session:
        yield session


def _normalize_url_key(url: str) -> str:
    raw = url.strip()
    p = urlparse(raw)
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    netloc = (p.netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    scheme = (p.scheme or "https").lower()
    return urlunparse((scheme, netloc, path, "", "", ""))


def dedupe_urls_preserve_order(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = u.strip()
        if not u:
            continue
        key = _normalize_url_key(u)
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


@router.post("")
async def create_batch(payload: CreateBatchRequest, session: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    url_strings = [str(u) for u in payload.urls]
    deduped = dedupe_urls_preserve_order(url_strings)
    if not deduped:
        raise HTTPException(400, "No valid URLs after dedupe")
    if len(deduped) > settings.bulk_max_urls_per_batch:
        raise HTTPException(
            400,
            f"At most {settings.bulk_max_urls_per_batch} URLs per batch (after dedupe); got {len(deduped)}",
        )

    opts = payload.options
    snapshot = opts.model_dump(mode="json")
    batch_name = (payload.name or "").strip()[:120] or None

    batch = Batch(name=batch_name, status="queued", options_snapshot=snapshot)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    assert batch.id is not None

    for i, url in enumerate(deduped):
        run = Run(
            subject_url=url,
            n_competitors=opts.n_competitors,
            style_guide_id=opts.style_guide_id,
            batch_id=batch.id,
            batch_index=i,
            status="pending",
        )
        session.add(run)
    session.commit()

    enqueue_batch(batch.id)
    return {
        "id": batch.id,
        "status": batch.status,
        "name": batch.name,
        "name": batch.name,
        "url_count": len(deduped),
        "deduped_from": len(url_strings),
    }


@router.get("")
def list_batches(session: Session = Depends(get_session)) -> list[dict]:
    batches = list(session.exec(select(Batch).order_by(desc(Batch.id))).all())
    for b in batches:
        if b.status == "running" and b.id is not None:
            maybe_autofinalize_stuck_batch(b.id)
    batches = list(session.exec(select(Batch).order_by(desc(Batch.id))).all())
    out: list[dict] = []
    for b in batches:
        runs = session.exec(select(Run).where(Run.batch_id == b.id)).all()
        total = len(runs)
        finished = sum(1 for r in runs if r.status in ("done", "skipped", "failed"))
        out.append(
            {
                "id": b.id,
                "status": b.status,
                "name": b.name,
                "total_urls": total,
                "finished_urls": finished,
                "error": b.error,
                "created_at": b.created_at.isoformat(),
                "updated_at": b.updated_at.isoformat(),
            }
        )
    return out


@router.post("/{batch_id}/reconcile")
def reconcile_batch(batch_id: int) -> dict:
    """Recompute batch status and error from child runs (fixes stuck `running` after worker errors)."""
    with Session(get_engine()) as session:
        if session.get(Batch, batch_id) is None:
            raise HTTPException(404, "Batch not found")
    finalize_batch_record(batch_id)
    with Session(get_engine()) as session:
        b = session.get(Batch, batch_id)
    if b is None:
        raise HTTPException(404, "Batch not found")
    return {"id": b.id, "status": b.status, "error": b.error}


@router.get("/{batch_id}")
def get_batch(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    maybe_autofinalize_stuck_batch(batch_id)
    session.expire_all()
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    runs = session.exec(
        select(Run).where(Run.batch_id == batch_id).order_by(Run.batch_index)
    ).all()
    total = len(runs)
    finished = sum(1 for r in runs if r.status in ("done", "skipped", "failed"))
    return {
        "id": batch.id,
        "status": batch.status,
        "name": batch.name,
        "error": batch.error,
        "options_snapshot": batch.options_snapshot,
        "total_urls": total,
        "finished_urls": finished,
        "progress_percent": round(100 * finished / total, 1) if total else 0.0,
        "created_at": batch.created_at.isoformat(),
        "updated_at": batch.updated_at.isoformat(),
        "runs": [
            {
                "id": r.id,
                "subject_url": r.subject_url,
                "status": r.status,
                "current_step": r.current_step,
                "terminal_reason": r.terminal_reason,
                "error": r.error,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in runs
        ],
    }


@router.get("/{batch_id}/export.csv")
def export_batch_csv(batch_id: int, session: Session = Depends(get_session)) -> Response:
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    runs = session.exec(
        select(Run).where(Run.batch_id == batch_id).order_by(Run.batch_index)
    ).all()
    run_ids = [r.id for r in runs if r.id is not None]

    outputs_by_run: dict[int, dict[int, dict | None]] = {}
    if run_ids:
        step_rows = session.exec(
            select(StepResult).where(
                StepResult.run_id.in_(run_ids),
                StepResult.step_no.in_((7, 8, 9)),
                StepResult.status == "completed",
            )
        ).all()
        for sr in step_rows:
            out = sr.output_json
            outputs_by_run.setdefault(sr.run_id, {})[sr.step_no] = out if isinstance(out, dict) else None

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "url", "title", "WYSIWYG", "HTML", "JSON-LD"])

    for r in runs:
        rid = r.id
        by_step = outputs_by_run.get(rid, {}) if rid is not None else {}
        s7 = by_step.get(7)
        s8 = by_step.get(8)
        s9 = by_step.get(9)

        title = ""
        wysiwyg = ""
        if isinstance(s7, dict):
            title = str(s7.get("h1") or "").strip()
            wysiwyg = final_copy_dict_to_wysiwyg_markdown(s7)

        html = ""
        if isinstance(s8, dict):
            html = str(s8.get("html") or "")

        json_ld = ""
        if s9 is not None:
            try:
                json_ld = json.dumps(s9, ensure_ascii=False)
            except TypeError:
                json_ld = str(s9)

        w.writerow(
            [
                rid if rid is not None else "",
                r.subject_url,
                title,
                wysiwyg,
                html,
                json_ld,
            ]
        )

    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch_id}.csv"'},
    )


def _serialize_step_row(sr: StepResult) -> dict:
    name = sr.step_name or ""
    if not name or name == "pending":
        name = _STEP_NAMES.get(sr.step_no, f"step_{sr.step_no}")
    return {
        "id": sr.id,
        "step_no": sr.step_no,
        "step_name": name,
        "status": sr.status,
        "output": sr.output_json,
        "duration_ms": sr.duration_ms,
        "model_used": sr.model_used,
        "error": sr.error,
        "updated_at": sr.updated_at.isoformat(),
    }


@router.get("/{batch_id}/report")
def get_batch_report(batch_id: int, session: Session = Depends(get_session)) -> dict:
    """Per-run pipeline outputs for batch results UI (steps 7–10 + sources for completed runs)."""
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    runs = session.exec(
        select(Run).where(Run.batch_id == batch_id).order_by(Run.batch_index)
    ).all()
    run_ids = [r.id for r in runs if r.id is not None]
    steps_by_run: dict[int, dict[int, StepResult]] = {}
    if run_ids:
        step_rows = session.exec(
            select(StepResult).where(
                StepResult.run_id.in_(run_ids),
                StepResult.step_no.in_(_REPORT_STEP_NOS),
                StepResult.status == "completed",
            )
        ).all()
        for sr in step_rows:
            if sr.run_id not in steps_by_run:
                steps_by_run[sr.run_id] = {}
            steps_by_run[sr.run_id][sr.step_no] = sr

    sources_by_run: dict[int, list[dict]] = {}
    if run_ids:
        source_rows = session.exec(
            select(Source).where(Source.run_id.in_(run_ids)).order_by(Source.run_id, Source.id)
        ).all()
        for src in source_rows:
            sources_by_run.setdefault(src.run_id, []).append(
                {
                    "id": src.id,
                    "url": src.url,
                    "kind": src.kind,
                    "title": src.title,
                    "classification": src.classification,
                    "notes": src.notes,
                    "fetched_at": src.fetched_at.isoformat(),
                }
            )

    out_runs: list[dict] = []
    for r in runs:
        rid = r.id
        entry: dict = {
            "id": rid,
            "subject_url": r.subject_url,
            "status": r.status,
            "terminal_reason": r.terminal_reason,
            "error": r.error,
            "current_step": r.current_step,
        }
        if rid is not None and rid in steps_by_run:
            ordered = []
            for step_no in _REPORT_STEP_NOS:
                sr = steps_by_run[rid].get(step_no)
                if sr is not None:
                    ordered.append(_serialize_step_row(sr))
            if ordered:
                entry["steps"] = ordered
                entry["sources"] = sources_by_run.get(rid, [])
        out_runs.append(entry)

    return {"batch_id": batch_id, "runs": out_runs}
