Compare the subject extract against the manufacturer-verified items and the competitor extracts.

A content gap is valid only when ALL of the following are true:
- It is missing or weak on the subject page
- It is product-specific (not generic category content)
- It helps a buyer identify, compare, select, install, evaluate, trust, or purchase the product
- It is verified by manufacturer documentation OR found in at least 2 independent exact-match competitor PDPs (different domains)

For each candidate gap, fill in:
- content_element: short description of the gap
- category: one of the allowed GapCategory enum values
- missing_from_subject: bool
- manufacturer_verified: bool
- competitor_count: int (count of distinct domains, NOT page count)
- competitor_sources: list of competitor URLs
- included: true ONLY if (manufacturer_verified OR competitor_count >= 2). The orchestrator re-validates this rule, but you must compute it correctly.
- reason: 1 sentence explanation
- proposed_value: optional concise value/text to use in the final copy

Add `excluded` rows for content found on competitors but excluded from the final copy (e.g., wrong-model claims, price, marketing fluff, unsupported safety claims). Use the GapCategory `Excluded Claim` for those.

If you find conflicting numeric values across sources, list them in `conflicts` (free-form strings), do NOT silently blend.
