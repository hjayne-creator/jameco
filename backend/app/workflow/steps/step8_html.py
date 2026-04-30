"""Step 8 - Render the FinalCopy as semantic HTML.

Done deterministically (no LLM) so the HTML is guaranteed to match the
WYSIWYG copy that the user approved at the previous checkpoint.
"""
from __future__ import annotations

from html import escape

from app.events import bus
from app.models.schemas import FinalCopy, HtmlCopy
from app.workflow.state import RunState


def _render_specs(specs) -> str:
    if not specs:
        return ""
    rows = []
    for s in specs:
        value = s.value
        if s.unit:
            value = f"{value} {s.unit}".strip()
        rows.append(
            f"      <tr><th>{escape(s.name)}</th><td>{escape(value)}</td></tr>"
        )
    return (
        "<table>\n"
        "  <thead>\n"
        "    <tr><th>Specification</th><th>Value</th></tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        + "\n".join(rows)
        + "\n  </tbody>\n</table>"
    )


def _render_features(features) -> str:
    if not features:
        return ""
    items = []
    for f in features:
        text = escape(f.feature)
        if f.benefit:
            text += f" \u2014 {escape(f.benefit)}"
        items.append(f"  <li>{text}</li>")
    return "<ul>\n" + "\n".join(items) + "\n</ul>"


def _render_simple_list(values) -> str:
    if not values:
        return ""
    return "<ul>\n" + "\n".join(f"  <li>{escape(v)}</li>" for v in values) + "\n</ul>"


def _render_faqs(faqs) -> str:
    if not faqs:
        return ""
    blocks = []
    for q in faqs:
        blocks.append(
            f"<h3>{escape(q.question)}</h3>\n<p>{escape(q.answer)}</p>"
        )
    return "\n".join(blocks)


def _render_concerns(concerns) -> str:
    if not concerns:
        return ""
    blocks = []
    for c in concerns:
        blocks.append(
            f"<h3>{escape(c.concern)}</h3>\n<p>{escape(c.response)}</p>"
        )
    return "\n".join(blocks)


def render(copy: FinalCopy) -> str:
    parts: list[str] = []
    parts.append(f"<h1>{escape(copy.h1)}</h1>")

    if copy.identity_block:
        parts.append("<ul>")
        for item in copy.identity_block:
            parts.append(f"  <li>{escape(item)}</li>")
        parts.append("</ul>")

    parts.append(f"<h2>{escape(copy.h2)}</h2>")

    if copy.overview:
        parts.append(f"<p>{escape(copy.overview)}</p>")

    if copy.features:
        parts.append("<h2>Key Features and Benefits</h2>")
        parts.append(_render_features(copy.features))

    if copy.applications:
        parts.append("<h2>Applications</h2>")
        parts.append(_render_simple_list(copy.applications))

    if copy.specifications:
        parts.append("<h2>Specifications</h2>")
        parts.append(_render_specs(copy.specifications))

    if copy.faqs:
        parts.append("<h2>Customer Questions</h2>")
        parts.append(_render_faqs(copy.faqs))

    if copy.customer_concerns:
        parts.append("<h2>Customer Concerns</h2>")
        parts.append(_render_concerns(copy.customer_concerns))

    return "\n".join(p for p in parts if p)


async def run(state: RunState, *, run_id: int) -> HtmlCopy:
    if state.final_copy is None:
        raise RuntimeError("Step 8 requires Step 7 output")
    await bus.publish(run_id, "step.progress", {"step_no": 8, "message": "Rendering HTML"})
    return HtmlCopy(html=render(state.final_copy))
