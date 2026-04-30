Review the manufacturer source pages below. For each source classify it as one of:
exact_current, exact_older, exact_regional, product_family, near_match, not_applicable.

Then extract:
- verified_specs (only specs that appear in exact_current or exact_older or exact_regional sources for the exact MPN/series; otherwise omit)
- verified_features (feature bullets clearly grounded in the manufacturer source)
- verified_certifications (compliance / certificate marks named explicitly)

Each item must include `sources` as a list of {kind: "manufacturer", url}.

If a numeric value differs across sources, note it in `notes` and prefer the most recent exact_current source. Never blend numeric ranges.
