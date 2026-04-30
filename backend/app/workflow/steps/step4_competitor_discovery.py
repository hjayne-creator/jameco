"""Step 4 - Competitor Discovery via SerpAPI."""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from app.adapters import SerpapiClient
from app.adapters.serpapi_client import OrganicResult
from app.events import bus
from app.models.schemas import CompetitorCandidate, CompetitorList
from app.workflow.state import RunState

logger = logging.getLogger(__name__)


# Domains to exclude entirely or treat as low-confidence (per the prompt's rules).
_EXCLUDED_DOMAINS = {
    "ebay.com", "wikipedia.org", "youtube.com", "reddit.com", "quora.com",
    "stackoverflow.com", "facebook.com", "instagram.com", "linkedin.com",
    "pinterest.com", "twitter.com", "x.com",
}
# Subject domain we always exclude (set dynamically below from the subject URL).

_LOW_CONFIDENCE_DOMAINS = {"amazon.com", "walmart.com", "alibaba.com", "aliexpress.com"}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _normalize_domain(d: str) -> str:
    return d[4:] if d.startswith("www.") else d


def _candidate_score(result: OrganicResult, mpn: str | None, brand: str | None) -> tuple[float, str | None]:
    domain = _normalize_domain(_domain(result.url))
    if not domain:
        return 0.0, "no domain"
    if domain in _EXCLUDED_DOMAINS:
        return 0.0, f"excluded domain {domain}"

    score = 0.0
    if mpn:
        mpn_l = mpn.lower()
        if mpn_l in (result.title or "").lower():
            score += 0.5
        if mpn_l in (result.url or "").lower():
            score += 0.3
        if mpn_l in (result.snippet or "").lower():
            score += 0.2
    if brand and brand.lower() in (result.title or "").lower():
        score += 0.1
    if domain in _LOW_CONFIDENCE_DOMAINS:
        score *= 0.5
    return min(score, 1.0), None


async def run(state: RunState, *, run_id: int) -> CompetitorList:
    if state.identity_lock is None:
        raise RuntimeError("Step 4 requires Step 2 output")

    serp = SerpapiClient()
    if not serp.configured:
        return CompetitorList(
            queries_run=[],
            candidates=[],
            requested_count=state.n_competitors,
            accepted_count=0,
        )

    identity = state.identity_lock
    queries: list[str] = []
    if identity.brand and identity.mpn:
        queries.append(f"{identity.brand} {identity.mpn}")
    if identity.manufacturer and identity.mpn and identity.manufacturer != identity.brand:
        queries.append(f"{identity.manufacturer} {identity.mpn}")
    if identity.mpn:
        queries.append(f'"{identity.mpn}"')
    if identity.product_type and identity.brand:
        queries.append(f"{identity.brand} {identity.product_type}")

    queries = [q for q in queries if q]

    subject_domain = _normalize_domain(_domain(state.subject_url))

    seen: dict[str, CompetitorCandidate] = {}
    for q in queries:
        await bus.publish(run_id, "step.progress", {"step_no": 4, "message": f"Searching: {q}"})
        try:
            results = await serp.search(q, num=10)
        except Exception as exc:
            logger.warning("Competitor search failed for %s: %s", q, exc)
            continue
        for r in results:
            url = r.url
            if not url or url in seen:
                continue
            domain = _normalize_domain(_domain(url))
            if domain == subject_domain:
                continue
            score, reject = _candidate_score(r, identity.mpn, identity.brand)
            cand = CompetitorCandidate(
                url=url,
                title=r.title,
                domain=domain,
                snippet=r.snippet,
                matched_query=q,
                confidence=score,
                rejected_reason=reject,
                accepted=False,
            )
            seen[url] = cand

    sorted_cands = sorted(seen.values(), key=lambda c: c.confidence, reverse=True)

    accept_target = state.n_competitors
    accepted = 0
    used_domains: set[str] = set()
    for c in sorted_cands:
        if c.rejected_reason:
            continue
        if c.confidence < 0.4:
            c.rejected_reason = "low confidence"
            continue
        if c.domain in used_domains:
            c.rejected_reason = "duplicate domain"
            continue
        if accepted >= accept_target:
            c.rejected_reason = "over target count"
            continue
        c.accepted = True
        used_domains.add(c.domain)
        accepted += 1

    return CompetitorList(
        queries_run=queries,
        candidates=sorted_cands,
        accepted_count=accepted,
        requested_count=accept_target,
    )
