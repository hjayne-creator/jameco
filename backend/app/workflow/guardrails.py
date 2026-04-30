"""Hard filters applied after generative steps to enforce the prompt's exclusions."""
from __future__ import annotations

import re
from typing import Iterable

from app.models.schemas import (
    FAQ,
    CustomerConcern,
    FeatureBullet,
    FinalCopy,
    GapRow,
    Specification,
)


# Patterns chosen to match common PDP phrasing without false-positives on legit
# specs (e.g., a "12V supply current" spec should not be filtered).
DENY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\$\s?\d", re.IGNORECASE),                        # prices like $12.99
    re.compile(r"\bUSD\b\s?\d", re.IGNORECASE),
    re.compile(r"\bin\s+stock\b", re.IGNORECASE),
    re.compile(r"\bout\s+of\s+stock\b", re.IGNORECASE),
    re.compile(r"\bback[\s-]?order(ed)?\b", re.IGNORECASE),
    re.compile(r"\blead\s+time\b", re.IGNORECASE),
    re.compile(r"\bships?\s+(in|within|today|tomorrow|same[\s-]?day)\b", re.IGNORECASE),
    re.compile(r"\bfree\s+shipping\b", re.IGNORECASE),
    re.compile(r"\btariff\b", re.IGNORECASE),
    re.compile(r"\bpromo(tion(al)?)?\b", re.IGNORECASE),
    re.compile(r"\bcoupon\b", re.IGNORECASE),
    re.compile(r"\bdiscount(ed)?\b", re.IGNORECASE),
    re.compile(r"\b(buy|order)\s+(now|today)\b", re.IGNORECASE),
    re.compile(r"\b(related|recommended|similar)\s+products\b", re.IGNORECASE),
    re.compile(r"\bcross[\s-]?sell\b", re.IGNORECASE),
    re.compile(r"\bsubstitute(s)?\s+available\b", re.IGNORECASE),
]


def find_violations(text: str) -> list[str]:
    if not text:
        return []
    return [pat.pattern for pat in DENY_PATTERNS if pat.search(text)]


def _scrub_str(text: str) -> tuple[str, list[str]]:
    violations = find_violations(text)
    if not violations:
        return text, []
    cleaned = text
    for pat in DENY_PATTERNS:
        cleaned = pat.sub("[redacted]", cleaned)
    return cleaned, violations


def _scrub_iterable(values: Iterable[str]) -> tuple[list[str], list[str]]:
    out: list[str] = []
    all_violations: list[str] = []
    for v in values:
        cleaned, vio = _scrub_str(v)
        out.append(cleaned)
        all_violations.extend(vio)
    return out, all_violations


def scrub_final_copy(copy: FinalCopy) -> tuple[FinalCopy, list[str]]:
    """Return a cleaned FinalCopy plus a list of violation patterns that fired.

    The cleaned copy is a deep-copied model to avoid mutating the caller's object.
    """
    violations: list[str] = []

    def s(text: str | None) -> str | None:
        if text is None:
            return None
        cleaned, vio = _scrub_str(text)
        violations.extend(vio)
        return cleaned

    h1 = s(copy.h1) or copy.h1
    h2 = s(copy.h2) or copy.h2
    overview = s(copy.overview) or copy.overview

    identity, vio = _scrub_iterable(copy.identity_block)
    violations.extend(vio)

    apps, vio = _scrub_iterable(copy.applications)
    violations.extend(vio)

    features: list[FeatureBullet] = []
    for f in copy.features:
        feat = s(f.feature) or f.feature
        ben = s(f.benefit) if f.benefit else f.benefit
        features.append(FeatureBullet(feature=feat, benefit=ben, sources=f.sources))

    specs: list[Specification] = []
    for sp in copy.specifications:
        name = s(sp.name) or sp.name
        value = s(sp.value) or sp.value
        unit = s(sp.unit) if sp.unit else sp.unit
        specs.append(Specification(name=name, value=value, unit=unit, sources=sp.sources))

    faqs: list[FAQ] = []
    for q in copy.faqs:
        faqs.append(
            FAQ(
                question=s(q.question) or q.question,
                answer=s(q.answer) or q.answer,
                sources=q.sources,
            )
        )

    concerns: list[CustomerConcern] = []
    for c in copy.customer_concerns:
        concerns.append(
            CustomerConcern(
                concern=s(c.concern) or c.concern,
                response=s(c.response) or c.response,
                sources=c.sources,
            )
        )

    cleaned = FinalCopy(
        h1=h1,
        identity_block=identity,
        h2=h2,
        overview=overview,
        features=features,
        applications=apps,
        specifications=specs,
        faqs=faqs,
        customer_concerns=concerns,
    )
    return cleaned, violations


def _final_copy_text(copy: FinalCopy) -> str:
    parts: list[str] = [copy.h1, copy.h2, copy.overview, *copy.identity_block, *copy.applications]
    for f in copy.features:
        parts.append(f.feature)
        if f.benefit:
            parts.append(f.benefit)
    for s in copy.specifications:
        parts.append(s.name)
        parts.append(s.value)
        if s.unit:
            parts.append(s.unit)
    for q in copy.faqs:
        parts.append(q.question)
        parts.append(q.answer)
    for c in copy.customer_concerns:
        parts.append(c.concern)
        parts.append(c.response)
    return " ".join(p for p in parts if p).lower()


def detect_excluded_leakage(copy: FinalCopy, excluded_rows: Iterable[GapRow]) -> list[str]:
    """Return the excluded gap row labels that appear in the final copy text.

    Used as a post-generation safety net: if the LLM ignored the instruction
    to drop excluded rows, we surface it as an audit note instead of silently
    publishing.
    """
    haystack = _final_copy_text(copy)
    leaked: list[str] = []
    for row in excluded_rows:
        candidates = []
        if row.proposed_value:
            candidates.append(row.proposed_value)
        candidates.append(row.content_element)
        for needle in candidates:
            if not needle or len(needle) < 6:
                continue
            if needle.lower() in haystack:
                leaked.append(needle)
                break
    return leaked


def remove_leaked_phrases(copy: FinalCopy, leaked: Iterable[str]) -> FinalCopy:
    """Strip leaked excluded phrases from the public-facing string fields.

    Conservative: replaces the offending phrase with an empty string. Surrounding
    sentences may end up choppy, which is intentional — the audit note tells the
    user to revisit the copy.
    """
    needles = [n for n in leaked if n and len(n) >= 6]
    if not needles:
        return copy

    def scrub(text: str) -> str:
        out = text
        for needle in needles:
            pattern = re.compile(re.escape(needle), re.IGNORECASE)
            out = pattern.sub("", out)
        return re.sub(r"\s{2,}", " ", out).strip(" ,.;:")

    return FinalCopy(
        h1=scrub(copy.h1),
        identity_block=[scrub(b) for b in copy.identity_block],
        h2=scrub(copy.h2),
        overview=scrub(copy.overview),
        features=[
            FeatureBullet(feature=scrub(f.feature), benefit=scrub(f.benefit) if f.benefit else None, sources=f.sources)
            for f in copy.features
        ],
        applications=[scrub(a) for a in copy.applications],
        specifications=[
            Specification(name=scrub(s.name), value=scrub(s.value), unit=s.unit, sources=s.sources)
            for s in copy.specifications
        ],
        faqs=[FAQ(question=scrub(q.question), answer=scrub(q.answer), sources=q.sources) for q in copy.faqs],
        customer_concerns=[
            CustomerConcern(concern=scrub(c.concern), response=scrub(c.response), sources=c.sources)
            for c in copy.customer_concerns
        ],
    )
