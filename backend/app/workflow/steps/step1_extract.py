"""Step 1 - Subject Page Extraction."""
from __future__ import annotations

import logging

from app.adapters import fetch_page
from app.events import bus
from app.models.schemas import SubjectExtract
from app.workflow.llm import call_json, role_cfg
from app.workflow.prompts import load_text
from app.workflow.sources import record_source
from app.workflow.state import RunState

logger = logging.getLogger(__name__)

PROMPT = load_text("step1_extract.md")
MAX_MD_CHARS = 50_000


async def run(state: RunState, *, run_id: int) -> SubjectExtract:
    await bus.publish(run_id, "step.progress", {"step_no": 1, "message": "Fetching subject page"})
    fetched = await fetch_page(state.subject_url)

    record_source(
        run_id=run_id,
        url=state.subject_url,
        kind="subject",
        title=fetched.title,
        classification="subject",
        raw_md=(fetched.markdown or "")[:20_000],
        notes=f"engine={fetched.source_engine}",
    )
    state.sources_used.append({"kind": "subject", "url": state.subject_url, "support": "Subject PDP extraction"})

    await bus.publish(run_id, "step.progress", {"step_no": 1, "message": "Extracting structured fields"})
    cfg = role_cfg("extraction")
    user = (
        f"Subject URL: {state.subject_url}\n"
        f"Page title: {fetched.title or ''}\n\n"
        f"--- BEGIN PAGE MARKDOWN ---\n{(fetched.markdown or '')[:MAX_MD_CHARS]}\n--- END PAGE MARKDOWN ---"
    )
    extract = await call_json(
        cfg, system=PROMPT, user=user, schema=SubjectExtract, max_tokens=8000
    )
    if not extract.url:
        extract.url = state.subject_url
    return extract
