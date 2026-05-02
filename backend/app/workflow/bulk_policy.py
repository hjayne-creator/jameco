"""Bulk batch policies: identity gates, competitor auto-accept."""
from __future__ import annotations

from urllib.parse import urlparse

from app.models.schemas import BulkOptions, CompetitorCandidate, CompetitorList, IdentityLock


def _nonempty(v: str | None) -> bool:
    return v is not None and str(v).strip() != ""


def identity_is_ambiguous(lock: IdentityLock) -> bool:
    return bool(lock.ambiguous)


def identity_effectively_empty(lock: IdentityLock) -> bool:
    """No usable primary identifiers for downstream search (bulk skip rule)."""
    if lock.ambiguous:
        return False
    return not any(
        (
            _nonempty(lock.brand),
            _nonempty(lock.manufacturer),
            _nonempty(lock.mpn),
            _nonempty(lock.sku),
            _nonempty(lock.gtin),
            _nonempty(lock.upc),
            _nonempty(lock.ean),
            _nonempty(lock.model_number),
        )
    )


def _normalize_domain(host: str) -> str:
    h = host.lower().strip()
    return h[4:] if h.startswith("www.") else h


def _blocklist_key(raw: str) -> str:
    s = raw.strip().lower()
    if not s:
        return ""
    if "://" in s:
        host = urlparse(s).netloc
        return _normalize_domain(host) if host else ""
    return _normalize_domain(s)


def _candidate_domain(c: CompetitorCandidate) -> str:
    if c.domain:
        return _normalize_domain(c.domain)
    try:
        host = urlparse(c.url).netloc
        return _normalize_domain(host) if host else ""
    except Exception:
        return ""


def apply_competitor_auto_policy(cl: CompetitorList, options: BulkOptions) -> CompetitorList:
    """Set `accepted`: drop blocklist, require confidence floor, then top `n_competitors` by confidence."""
    for c in cl.candidates:
        c.accepted = False

    block = {_blocklist_key(d) for d in options.domain_blocklist}
    block.discard("")

    eligible: list[CompetitorCandidate] = []
    for c in cl.candidates:
        dom = _candidate_domain(c)
        if dom in block:
            continue
        if c.confidence < options.min_competitor_confidence:
            continue
        eligible.append(c)

    eligible.sort(key=lambda x: x.confidence, reverse=True)
    k = options.n_competitors
    keep_urls = {c.url for c in eligible[:k]}

    for c in cl.candidates:
        c.accepted = c.url in keep_urls

    cl.accepted_count = sum(1 for c in cl.candidates if c.accepted)
    cl.requested_count = options.n_competitors
    return cl
