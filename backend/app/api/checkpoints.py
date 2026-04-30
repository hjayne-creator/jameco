"""Checkpoint approval endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import CheckpointApproval
from app.workflow.orchestrator import CHECKPOINT_TO_STEP, approve_checkpoint

router = APIRouter()


@router.post("/{run_id}/checkpoints/{name}/approve")
async def approve(run_id: int, name: str, payload: CheckpointApproval) -> dict:
    if name not in CHECKPOINT_TO_STEP:
        raise HTTPException(400, f"Unknown checkpoint: {name}")
    try:
        await approve_checkpoint(run_id, name, payload.edited_payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "checkpoint": name}
