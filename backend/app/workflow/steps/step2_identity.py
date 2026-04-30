"""Step 2 - Product Identity Lock."""
from __future__ import annotations

from app.events import bus
from app.models.schemas import IdentityLock
from app.workflow.llm import call_json, role_cfg
from app.workflow.prompts import load_text
from app.workflow.state import RunState

PROMPT = load_text("step2_identity.md")


async def run(state: RunState, *, run_id: int) -> IdentityLock:
    if state.subject_extract is None:
        raise RuntimeError("Step 2 requires Step 1 output")

    await bus.publish(run_id, "step.progress", {"step_no": 2, "message": "Locking product identity"})
    cfg = role_cfg("extraction")

    user = (
        "Subject extract (JSON):\n"
        f"{state.subject_extract.model_dump_json(indent=2)}\n"
    )
    identity = await call_json(
        cfg, system=PROMPT, user=user, schema=IdentityLock, max_tokens=2000
    )
    return identity
