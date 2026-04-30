Lock the exact product identity for downstream search.

Use ONLY the subject extract provided. Prefer values clearly tied to the product (H1, structured data, spec rows). If multiple candidate MPNs appear (e.g., a series MPN vs. a configured MPN), pick the most specific one and note ambiguity.

If identity cannot be confidently determined (no MPN AND no SKU AND no model_number), set ambiguous=true and list what is missing in ambiguity_notes.

Return JSON matching the IdentityLock schema.
