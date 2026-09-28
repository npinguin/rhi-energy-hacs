"""Structural presence helpers for optional physical Energy capabilities."""
from __future__ import annotations

from typing import Any

from .canonical_semantics import optional_physical_input

_OBJECT_CLASSES = {
    "battery_system": {"battery", "battery_system"},
    "gas_meter": {"gas_meter"},
    "price_source": {"price_source"},
    "solar_production": {"solar_inverter", "solar_source", "solar_production"},
    "grid_connection": {"grid_connection"},
}

def concept_present(model: dict[str, Any] | None, concept: str, assets: list[dict[str, Any]]) -> bool:
    """Return structural presence from accepted Energy truth, never telemetry."""
    model = model or {}
    if concept in set(model.get("explicitly_absent_concepts") or []):
        return False
    if concept in (model.get("concepts") or {}):
        return True
    object_classes = _OBJECT_CLASSES.get(concept, {concept})
    return any(str(row.get("object_class") or "") in object_classes for row in assets)

def physical_input(
    model: dict[str, Any] | None,
    concept: str,
    fact_key: str,
    facts: dict[str, Any],
    assets: list[dict[str, Any]],
) -> float | None:
    """Zero only structurally absent optional physics; preserve unavailable as unknown."""
    return optional_physical_input(
        facts.get(fact_key),
        concept_absent=not concept_present(model, concept, assets),
    )


def experience_presence(
    model: dict[str, Any] | None,
    assets: list[dict[str, Any]],
    flexible: list[dict[str, Any]],
    connections: list[dict[str, Any]],
) -> dict[str, bool]:
    """Publish product structural presence independently from runtime availability."""
    return {
        "grid": concept_present(model, "grid_connection", assets),
        "solar": concept_present(model, "solar_production", assets),
        "battery": concept_present(model, "battery_system", assets),
        "gas": concept_present(model, "gas_meter", assets),
        "pricing": concept_present(model, "price_source", assets),
        "flexible_loads": bool(flexible or connections),
    }
