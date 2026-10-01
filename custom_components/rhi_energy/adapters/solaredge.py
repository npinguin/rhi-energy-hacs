"""Legacy SolarEdge Energy value conventions."""
from __future__ import annotations

from typing import Any


def normalization_semantics(role: str) -> dict[str, str]:
    if role == "grid.net_power_kw":
        return {
            "source_semantics": "signed SolarEdge grid power",
            "source_sign_convention": "positive=export, negative=import",
            "canonical_sign_convention": "positive=import, negative=export",
            "transform": "negate",
        }
    return {"transform": "identity"}


def normalize(role: str, value: Any, context: dict[str, Any]) -> Any:
    if value is None:
        return None
    if role == "grid.net_power_kw":
        return -float(value)
    return value
