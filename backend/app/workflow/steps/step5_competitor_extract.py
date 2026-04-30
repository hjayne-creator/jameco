"""Step 5 - Competitor Extraction (parallel)."""
from __future__ import annotations

import asyncio
import logging

from app.adapters import fetch_page
from app.events import bus
from app.models.schemas import CompetitorExtract, CompetitorExtracts
from app.workflow.llm import call_json, role_cfg
from app.workflow.prompts import load_text
from app.workflow.sources import record_source
from app.workflow.state import RunState

logger = logging.getLogger(__name__)

PROMPT = load_text("step5_competitor.md")
PER_PAGE_MD_CHARS = 18_000
CONCURRENCY = 4


async def _process_one(
    cand_url: str,
    cand_title: str,
    state: RunState,
    run_id: int,
    semaphore: asyncio.Semaphore,
) -> CompetitorExtract | None:
    async with semaphore:
        try:
            await bus.publish(
                run_id,
                "step.progress",
                {"step_no": 5, "message": f"Fetching {cand_url}"},
            )
            res = await fetch_page(cand_url)
        except Exception as exc:
            logger.warning("Competitor fetch failed for %s: %s", cand_url, exc)
            return None

        record_source(
            run_id=run_id,
            url=cand_url,
            kind="competitor",
            title=res.title or cand_title,
            raw_md=(res.markdown or "")[:15_000],
            notes=f"engine={res.source_engine}",
        )
        state.sources_used.append(
            {"kind": "competitor", "url": cand_url, "support": "Competitor PDP for content gap discovery"}
        )

        cfg = role_cfg("extraction")
        identity_json = state.identity_lock.model_dump_json() if state.identity_lock else "{}"
        user = (
            f"Subject identity (must match):\n{identity_json}\n\n"
            f"Competitor URL: {cand_url}\n\n"
            f"--- BEGIN PAGE MARKDOWN ---\n{(res.markdown or '')[:PER_PAGE_MD_CHARS]}\n--- END PAGE MARKDOWN ---"
        )
        try:
            extract = await call_json(
                cfg, system=PROMPT, user=user, schema=CompetitorExtract, max_tokens=6000
            )
        except Exception as exc:
            logger.warning("Competitor LLM extraction failed for %s: %s", cand_url, exc)
            return None
        if not extract.url:
            extract.url = cand_url
        return extract


async def run(state: RunState, *, run_id: int) -> CompetitorExtracts:
    if state.competitor_list is None:
        raise RuntimeError("Step 5 requires Step 4 output")

    accepted = [c for c in state.competitor_list.candidates if c.accepted]
    if not accepted:
        return CompetitorExtracts(extracts=[])

    semaphore = asyncio.Semaphore(CONCURRENCY)
    coros = [
        _process_one(c.url, c.title, state, run_id, semaphore) for c in accepted
    ]
    results = await asyncio.gather(*coros)
    extracts = [r for r in results if r is not None]
    return CompetitorExtracts(extracts=extracts)
