"""Step 6 - Gap Validation.

The LLM proposes the gap table. We then re-validate every row against the
strict rule (manufacturer_verified OR competitor_count >= 2 distinct domains)
in code so that no included row can pass review just because the LLM said so.
"""
from __future__ import annotations

from urllib.parse import urlparse

from app.events import bus
from app.models.schemas import GapRow, GapValidation
from app.workflow.llm import call_json, role_cfg
from app.workflow.prompts import load_text
from app.workflow.state import RunState

PROMPT = load_text("step6_gaps.md")


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _enforce_inclusion_rules(rows: list[GapRow]) -> list[GapRow]:
    enforced: list[GapRow] = []
    for row in rows:
        unique_domains = {_domain(u) for u in row.competitor_sources if u}
        unique_domains.discard("")
        true_count = len(unique_domains)
        if row.competitor_count != true_count:
            row.competitor_count = true_count
        allowed = row.manufacturer_verified or true_count >= 2
        if not allowed:
            row.included = False
            row.reason = (
                row.reason
                + " | Auto-excluded: not manufacturer-verified and fewer than 2 distinct competitor domains."
            )
        enforced.append(row)
    return enforced


async def run(state: RunState, *, run_id: int) -> GapValidation:
    if state.subject_extract is None or state.competitor_extracts is None:
        raise RuntimeError("Step 6 requires Steps 1 and 5 outputs")

    await bus.publish(run_id, "step.progress", {"step_no": 6, "message": "Computing content gaps"})

    cfg = role_cfg("reasoning")
    manufacturer_json = (
        state.manufacturer.model_dump_json(indent=2)
        if state.manufacturer
        else "{}"
    )
    user = (
        "Subject extract:\n" + state.subject_extract.model_dump_json(indent=2)
        + "\n\nManufacturer-verified items:\n" + manufacturer_json
        + "\n\nCompetitor extracts:\n"
        + state.competitor_extracts.model_dump_json(indent=2)
    )
    raw = await call_json(
        cfg, system=PROMPT, user=user, schema=GapValidation, max_tokens=8000
    )
    raw.rows = _enforce_inclusion_rules(raw.rows)
    return raw
