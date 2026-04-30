"""Step 7 - Final WYSIWYG PDP Copy."""
from __future__ import annotations

from app.events import bus
from app.models.schemas import FinalCopy
from app.workflow.guardrails import (
    detect_excluded_leakage,
    remove_leaked_phrases,
    scrub_final_copy,
)
from app.workflow.llm import call_json, role_cfg
from app.workflow.prompts import load_text
from app.workflow.state import RunState

PROMPT = load_text("step7_copy.md")


async def run(state: RunState, *, run_id: int) -> FinalCopy:
    if (
        state.subject_extract is None
        or state.gap_validation is None
        or state.identity_lock is None
    ):
        raise RuntimeError("Step 7 requires Steps 1, 2 and 6 outputs")

    await bus.publish(run_id, "step.progress", {"step_no": 7, "message": "Generating final copy"})

    cfg = role_cfg("writing")

    included_rows = [r for r in state.gap_validation.rows if r.included]
    excluded_rows = [r for r in state.gap_validation.rows if not r.included]

    style_block = (
        f"\n\nSTYLE GUIDE:\n{state.style_guide_text}\n"
        if state.style_guide_text
        else ""
    )

    user = (
        "Identity:\n" + state.identity_lock.model_dump_json(indent=2)
        + "\n\nSubject extract:\n" + state.subject_extract.model_dump_json(indent=2)
        + (
            "\n\nManufacturer-verified items:\n" + state.manufacturer.model_dump_json(indent=2)
            if state.manufacturer else ""
        )
        + "\n\nIncluded gap rows:\n"
        + "\n".join(r.model_dump_json() for r in included_rows)
        + "\n\nExcluded gap rows (DO NOT USE):\n"
        + "\n".join(r.model_dump_json() for r in excluded_rows)
        + style_block
    )

    raw = await call_json(
        cfg, system=PROMPT, user=user, schema=FinalCopy, max_tokens=6000, temperature=0.2
    )
    cleaned, violations = scrub_final_copy(raw)
    if violations:
        state.audit_notes.append(
            "Deny-list filter triggered in final copy: " + ", ".join(sorted(set(violations)))
        )

    leaked = detect_excluded_leakage(cleaned, excluded_rows)
    if leaked:
        state.audit_notes.append(
            "Excluded gap content was detected in generated final copy and removed: "
            + "; ".join(leaked)
        )
        cleaned = remove_leaked_phrases(cleaned, leaked)
    return cleaned
