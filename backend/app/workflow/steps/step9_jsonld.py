"""Step 9 - JSON-LD Product schema.

Built deterministically from the verified inputs to guarantee no fabricated
fields. Inspired by the prompt list under additionalProperty.
"""
from __future__ import annotations

from app.events import bus
from app.workflow.state import RunState

# Specs that should be promoted into additionalProperty if available
_PROMOTED_PROPERTY_NAMES = {
    "voltage", "current", "power", "input voltage", "frequency", "efficiency",
    "dimensions", "weight", "mounting", "mounting style", "connector type",
    "operating temperature", "cooling method", "protection functions",
    "certifications", "warranty",
}


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def _spec_to_property(name: str, value: str, unit: str | None) -> dict:
    if unit:
        value = f"{value} {unit}".strip()
    prop: dict = {
        "@type": "PropertyValue",
        "name": name,
        "value": value,
    }
    if unit:
        prop["unitText"] = unit
    return prop


async def run(state: RunState, *, run_id: int) -> dict:
    if state.identity_lock is None:
        raise RuntimeError("Step 9 requires Step 2 output")

    await bus.publish(run_id, "step.progress", {"step_no": 9, "message": "Building JSON-LD"})

    identity = state.identity_lock
    final_copy = state.final_copy

    schema_obj: dict = {
        "@context": "https://schema.org",
        "@type": "Product",
    }

    if final_copy and final_copy.h1:
        schema_obj["name"] = final_copy.h1
    elif identity.brand and identity.mpn:
        schema_obj["name"] = f"{identity.brand} {identity.mpn}".strip()

    if identity.brand:
        schema_obj["brand"] = {"@type": "Brand", "name": identity.brand}
    if identity.manufacturer:
        schema_obj["manufacturer"] = {"@type": "Organization", "name": identity.manufacturer}
    if identity.mpn:
        schema_obj["mpn"] = identity.mpn
    if identity.sku:
        schema_obj["sku"] = identity.sku
    if identity.model_number:
        schema_obj["model"] = identity.model_number
    if identity.product_type:
        schema_obj["category"] = identity.product_type
    if identity.gtin:
        schema_obj["gtin"] = identity.gtin

    if state.subject_url:
        schema_obj["url"] = state.subject_url

    if final_copy and final_copy.overview:
        schema_obj["description"] = final_copy.overview

    properties: list[dict] = []
    seen_names: set[str] = set()
    spec_pool = []
    if final_copy and final_copy.specifications:
        spec_pool.extend(final_copy.specifications)
    if state.manufacturer and state.manufacturer.verified_specs:
        spec_pool.extend(state.manufacturer.verified_specs)

    for spec in spec_pool:
        key = _norm(spec.name)
        if not key or key in seen_names:
            continue
        seen_names.add(key)
        if any(p in key for p in _PROMOTED_PROPERTY_NAMES) or len(properties) < 12:
            properties.append(_spec_to_property(spec.name, spec.value, spec.unit))

    if state.manufacturer and state.manufacturer.verified_certifications:
        certs = ", ".join(state.manufacturer.verified_certifications)
        if "certifications" not in seen_names:
            properties.append({
                "@type": "PropertyValue",
                "name": "Certifications",
                "value": certs,
            })

    if properties:
        schema_obj["additionalProperty"] = properties

    return schema_obj
