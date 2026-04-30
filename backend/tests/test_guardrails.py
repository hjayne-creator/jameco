"""Guardrail tests.

Two pieces:
1. The deny-list scrubber redacts price / stock / lead-time / shipping / promo phrases.
2. The orchestrator-style integration: when running step 7 with stub inputs,
   no excluded gap row content survives in the final copy.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.models.schemas import (
    FAQ,
    CustomerConcern,
    FeatureBullet,
    FinalCopy,
    GapRow,
    GapValidation,
    IdentityLock,
    Specification,
    SubjectExtract,
)
from app.workflow.guardrails import find_violations, scrub_final_copy
from app.workflow.state import RunState


def test_deny_list_detects_common_violations():
    cases = [
        "Only $19.99 today!",
        "in stock and ready",
        "Ships within 24 hours",
        "Lead time: 6 weeks",
        "Free shipping on orders over $50",
        "promo code SAVE10",
        "related products you might like",
        "Order now and save",
    ]
    for text in cases:
        assert find_violations(text), f"Expected at least one violation in {text!r}"


def test_deny_list_does_not_redact_legit_specs():
    safe = [
        "12 V supply current",
        "Operating temperature -40 to 85 C",
        "Mounting holes spaced 25 mm apart",
        "RoHS compliant",
    ]
    for text in safe:
        assert not find_violations(text), f"Did not expect violation in {text!r}"


def test_scrub_final_copy_redacts_price_in_overview():
    copy = FinalCopy(
        h1="Acme Widget",
        identity_block=["Brand: Acme"],
        h2="Acme Widget WGT-100",
        overview="The Acme Widget is industrial grade. Only $99 today, ships within 24 hours.",
        features=[FeatureBullet(feature="Sealed enclosure", benefit="Resists dust ingress")],
        applications=["Industrial control panels"],
        specifications=[Specification(name="Voltage", value="12", unit="V")],
        faqs=[],
        customer_concerns=[],
    )
    cleaned, violations = scrub_final_copy(copy)
    assert violations, "Expected violations to fire"
    assert "$99" not in cleaned.overview
    assert "ships within" not in cleaned.overview.lower()
    assert "12" in cleaned.specifications[0].value
    assert cleaned.features[0].feature == "Sealed enclosure"


@pytest.mark.asyncio
async def test_step7_does_not_emit_excluded_gap_content():
    """Even if the LLM ignores instructions and emits an excluded phrase, the
    code-side detector strips it from the published copy and writes an audit
    note so the user is warned.
    """
    from app.workflow.steps import step7_final_copy

    state = RunState(
        run_id=1,
        subject_url="https://example.com/p/widget",
        n_competitors=3,
        style_guide_text="",
    )
    state.subject_extract = SubjectExtract(url=state.subject_url, brand="Acme")
    state.identity_lock = IdentityLock(brand="Acme", mpn="WGT-100", product_type="Widget")
    state.gap_validation = GapValidation(
        rows=[
            GapRow(
                content_element="IP65 enclosure rating",
                category="Safety / Compliance Note",
                missing_from_subject=True,
                manufacturer_verified=True,
                competitor_count=2,
                competitor_sources=["https://a.com/x", "https://b.com/y"],
                included=True,
                reason="MFR verified.",
                proposed_value="IP65",
            ),
            GapRow(
                content_element="Lifetime free replacement guarantee",
                category="Excluded Claim",
                missing_from_subject=True,
                manufacturer_verified=False,
                competitor_count=1,
                competitor_sources=["https://random.com/z"],
                included=False,
                reason="Not MFR-verified, only one source.",
                proposed_value="Lifetime free replacement",
            ),
        ],
        excluded=[],
        conflicts=[],
    )

    fake_copy = FinalCopy(
        h1="Acme WGT-100 Widget",
        identity_block=["Brand: Acme", "MPN: WGT-100"],
        h2="Acme Widget WGT-100",
        overview="Industrial widget rated IP65. Backed by lifetime free replacement guarantee.",
        features=[FeatureBullet(feature="IP65 enclosure", benefit="Protects against dust and water")],
        applications=["Industrial panels"],
        specifications=[Specification(name="Voltage", value="12", unit="V")],
        faqs=[],
        customer_concerns=[],
    )

    async def fake_call_json(*args, **kwargs):
        return fake_copy

    with patch.object(step7_final_copy, "call_json", side_effect=fake_call_json):
        result = await step7_final_copy.run(state, run_id=1)

    excluded_phrases = [
        r.proposed_value or r.content_element
        for r in state.gap_validation.rows
        if not r.included and (r.proposed_value or r.content_element)
    ]
    rendered = " ".join(
        [
            result.h1,
            result.h2,
            result.overview,
            *result.identity_block,
            *result.applications,
            *(f.feature for f in result.features),
            *((f.benefit or "") for f in result.features),
        ]
    ).lower()

    contamination = [p for p in excluded_phrases if p.lower() in rendered]
    assert not contamination, (
        f"Excluded gap content leaked into final copy. Leaked: {contamination!r}"
    )

    # The included content must still survive
    assert "ip65" in rendered

    # And the user must be warned via audit notes
    assert any("Excluded gap content was detected" in n for n in state.audit_notes), (
        f"Expected an audit note about leaked excluded content. Notes: {state.audit_notes}"
    )
