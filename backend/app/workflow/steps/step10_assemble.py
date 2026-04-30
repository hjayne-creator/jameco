"""Step 10 - Assemble the final user-facing output bundle."""
from __future__ import annotations

from app.events import bus
from app.models.schemas import FinalOutput, HtmlCopy
from app.workflow.state import RunState


def _summary_text(state: RunState) -> str:
    parts: list[str] = []
    parts.append(f"Subject URL: {state.subject_url}")
    if state.identity_lock:
        identity = state.identity_lock
        bits = []
        if identity.brand:
            bits.append(f"brand={identity.brand}")
        if identity.mpn:
            bits.append(f"mpn={identity.mpn}")
        if identity.product_type:
            bits.append(f"type={identity.product_type}")
        if bits:
            parts.append("Identity: " + ", ".join(bits))
    if state.competitor_list:
        parts.append(
            f"Competitor PDPs reviewed: {state.competitor_list.accepted_count} of {state.competitor_list.requested_count} requested"
        )
    if state.manufacturer:
        parts.append(f"Manufacturer sources used: {len(state.manufacturer.sources)}")
    if state.gap_validation:
        included = sum(1 for r in state.gap_validation.rows if r.included)
        excluded = len(state.gap_validation.rows) - included
        parts.append(f"Gap rows: {included} included, {excluded} excluded; {len(state.gap_validation.excluded)} explicit exclusions")
    return "\n".join(parts)


def _source_quality_notes(state: RunState) -> str:
    lines: list[str] = []
    if state.manufacturer and state.manufacturer.notes:
        lines.extend(state.manufacturer.notes)
    if state.gap_validation and state.gap_validation.conflicts:
        lines.append("Conflicts flagged:")
        lines.extend(f"  - {c}" for c in state.gap_validation.conflicts)
    if state.audit_notes:
        lines.extend(state.audit_notes)
    if not lines:
        lines.append("No source quality issues recorded.")
    return "\n".join(lines)


async def run(state: RunState, *, run_id: int) -> FinalOutput:
    if (
        state.identity_lock is None
        or state.gap_validation is None
        or state.final_copy is None
        or state.html_copy is None
        or state.json_ld is None
    ):
        raise RuntimeError("Step 10 requires all previous steps")

    await bus.publish(run_id, "step.progress", {"step_no": 10, "message": "Assembling final output"})

    return FinalOutput(
        research_summary=_summary_text(state),
        identity_lock=state.identity_lock,
        source_quality_notes=_source_quality_notes(state),
        gap_validation=state.gap_validation,
        excluded=state.gap_validation.excluded,
        final_copy=state.final_copy,
        html_copy=state.html_copy,
        json_ld=state.json_ld,
        sources=state.sources_used,
    )
