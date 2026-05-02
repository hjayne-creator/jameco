"""Build WYSIWYG markdown from FinalCopy JSON (same structure as frontend FinalOutputTabs)."""
from __future__ import annotations

from typing import Any


def final_copy_dict_to_wysiwyg_markdown(final_copy: dict[str, Any] | None) -> str:
    if not final_copy:
        return ""
    lines: list[str] = []
    h1 = final_copy.get("h1") or ""
    lines.append(f"# {h1}")

    identity_block = final_copy.get("identity_block") or []
    if isinstance(identity_block, list):
        for b in identity_block:
            if b:
                lines.append(f"- {b}")

    lines.append("")
    h2 = final_copy.get("h2") or ""
    lines.append(f"## {h2}")

    overview = final_copy.get("overview")
    if overview:
        lines.extend(["", overview])

    features = final_copy.get("features") or []
    if isinstance(features, list) and features:
        lines.extend(["", "## Key Features and Benefits"])
        for f in features:
            if isinstance(f, dict):
                feat = f.get("feature") or ""
                benefit = f.get("benefit")
                lines.append(f"- {feat}" + (f" — {benefit}" if benefit else ""))

    applications = final_copy.get("applications") or []
    if isinstance(applications, list) and applications:
        lines.extend(["", "## Applications"])
        for a in applications:
            if a:
                lines.append(f"- {a}")

    specifications = final_copy.get("specifications") or []
    if isinstance(specifications, list) and specifications:
        lines.extend(["", "## Specifications", "", "| Specification | Value |", "| --- | --- |"])
        for s in specifications:
            if isinstance(s, dict):
                name = s.get("name") or ""
                val = s.get("value") or ""
                unit = s.get("unit")
                v = f"{val} {unit}".strip() if unit else val
                lines.append(f"| {name} | {v} |")

    faqs = final_copy.get("faqs") or []
    if isinstance(faqs, list) and faqs:
        lines.extend(["", "## Customer Questions"])
        for q in faqs:
            if isinstance(q, dict):
                lines.extend(["", f"### {q.get('question') or ''}", "", q.get("answer") or ""])

    concerns = final_copy.get("customer_concerns") or []
    if isinstance(concerns, list) and concerns:
        lines.extend(["", "## Customer Concerns"])
        for c in concerns:
            if isinstance(c, dict):
                lines.extend(["", f"### {c.get('concern') or ''}", "", c.get("response") or ""])

    return "\n".join(lines)
