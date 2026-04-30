"""Step 3 - Manufacturer Verification.

Strategy:
- Use SerpAPI to find official manufacturer pages (product page, datasheet) for the
  exact MPN. Detect "official" candidates by domain heuristic (manufacturer name in
  domain) plus filetype:pdf for datasheets.
- Fetch up to 4 of those pages with the fetcher (markdown).
- Hand the markdown bundle to the LLM to classify + extract verified specs/features.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Iterable

from app.adapters import SerpapiClient, fetch_page
from app.adapters.serpapi_client import OrganicResult
from app.events import bus
from app.models.schemas import ManufacturerVerification
from app.workflow.llm import call_json, role_cfg
from app.workflow.prompts import load_text
from app.workflow.sources import record_source
from app.workflow.state import RunState

logger = logging.getLogger(__name__)

PROMPT = load_text("step3_manufacturer.md")
MAX_FETCH = 4
PER_PAGE_MD_CHARS = 18_000


_NON_MFR_DOMAINS = {
    "amazon", "ebay", "alibaba", "aliexpress", "walmart",
    "wikipedia", "youtube", "reddit", "facebook", "linkedin",
    "digikey", "mouser", "newark", "arrow", "rs-online", "jameco",
    "octopart", "findchips", "tme", "futureelectronics",
}


def _domain_root(url: str) -> str:
    if "//" not in url:
        return url
    host = url.split("//", 1)[1].split("/", 1)[0]
    parts = host.lower().split(".")
    if len(parts) >= 2:
        return parts[-2]
    return host


def _looks_like_manufacturer(result: OrganicResult, brand: str | None, manufacturer: str | None) -> bool:
    domain_root = _domain_root(result.url)
    if domain_root in _NON_MFR_DOMAINS:
        return False
    needles = [n for n in [brand, manufacturer] if n]
    if not needles:
        return False
    for n in needles:
        token = re.sub(r"[^a-z0-9]+", "", n.lower())
        if token and token in domain_root:
            return True
    return False


async def run(state: RunState, *, run_id: int) -> ManufacturerVerification:
    if state.identity_lock is None:
        raise RuntimeError("Step 3 requires Step 2 output")

    serp = SerpapiClient()
    if not serp.configured:
        await bus.publish(
            run_id,
            "step.progress",
            {"step_no": 3, "message": "SerpAPI not configured; skipping manufacturer discovery"},
        )
        return ManufacturerVerification(notes=["SerpAPI not configured; manufacturer step skipped"])

    identity = state.identity_lock
    queries: list[str] = []
    if identity.brand and identity.mpn:
        queries.append(f"{identity.brand} {identity.mpn} datasheet")
        queries.append(f"{identity.brand} {identity.mpn} site:{_brand_site_hint(identity.brand)}")
    if identity.manufacturer and identity.mpn and identity.manufacturer != identity.brand:
        queries.append(f"{identity.manufacturer} {identity.mpn} datasheet")
    if identity.mpn:
        queries.append(f'"{identity.mpn}" filetype:pdf')

    queries = [q for q in queries if q]

    candidates: list[OrganicResult] = []
    seen_urls: set[str] = set()
    for q in queries:
        await bus.publish(run_id, "step.progress", {"step_no": 3, "message": f"Searching: {q}"})
        try:
            results = await serp.search(q, num=10)
        except Exception as exc:
            logger.warning("Manufacturer search failed for %s: %s", q, exc)
            continue
        for r in results:
            if r.url in seen_urls:
                continue
            seen_urls.add(r.url)
            if _looks_like_manufacturer(r, identity.brand, identity.manufacturer) or r.url.lower().endswith(".pdf"):
                candidates.append(r)

    candidates = candidates[:MAX_FETCH]

    if not candidates:
        return ManufacturerVerification(
            notes=["No high-confidence manufacturer pages found via search."]
        )

    fetched_pages: list[tuple[OrganicResult, str]] = []
    for cand in candidates:
        if cand.url.lower().endswith(".pdf"):
            await bus.publish(
                run_id,
                "step.progress",
                {"step_no": 3, "message": f"Skipping PDF (no PDF parser in fetcher): {cand.url}"},
            )
            record_source(
                run_id=run_id,
                url=cand.url,
                kind="manufacturer",
                title=cand.title,
                classification="exact_current",
                notes="PDF datasheet (not parsed in v1; URL retained for sources list)",
            )
            state.sources_used.append(
                {"kind": "manufacturer", "url": cand.url, "support": "Datasheet (linked, not parsed in v1)"}
            )
            continue
        try:
            await bus.publish(run_id, "step.progress", {"step_no": 3, "message": f"Fetching {cand.url}"})
            res = await fetch_page(cand.url)
        except Exception as exc:
            logger.warning("Manufacturer fetch failed for %s: %s", cand.url, exc)
            continue
        record_source(
            run_id=run_id,
            url=cand.url,
            kind="manufacturer",
            title=res.title or cand.title,
            classification=None,
            raw_md=(res.markdown or "")[:15_000],
            notes=f"engine={res.source_engine}",
        )
        state.sources_used.append({"kind": "manufacturer", "url": cand.url, "support": "Manufacturer source page"})
        fetched_pages.append((cand, (res.markdown or "")[:PER_PAGE_MD_CHARS]))

    if not fetched_pages:
        return ManufacturerVerification(
            sources=[],
            notes=["Manufacturer candidates found but none could be fetched as HTML/markdown."],
        )

    cfg = role_cfg("reasoning")
    user = (
        f"Identity:\n{identity.model_dump_json(indent=2)}\n\n"
        + "\n\n".join(
            f"--- BEGIN SOURCE {i+1} ({c.url}) ---\n{md}\n--- END SOURCE {i+1} ---"
            for i, (c, md) in enumerate(fetched_pages)
        )
    )
    verification = await call_json(
        cfg, system=PROMPT, user=user, schema=ManufacturerVerification, max_tokens=6000
    )
    return verification


def _brand_site_hint(brand: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "", brand.lower())
    return f"{token}.com" if token else ""
