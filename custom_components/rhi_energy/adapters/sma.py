"""SMA Energy value and sign semantics."""
from __future__ import annotations
from typing import Any


def normalization_semantics(role: str) -> dict[str, str]:
    if role == "solar.power_kw":
        return {
            "source_semantics": "explicit photovoltaic production power",
            "source_sign_convention": "non-negative generation",
            "canonical_sign_convention": "non-negative generation",
            "transform": "identity",
        }
    if role == "solar.ac_power_kw":
        return {
            "source_semantics": "inverter AC production power",
            "source_sign_convention": "non-negative generation",
            "canonical_sign_convention": "non-negative generation",
            "transform": "identity",
        }
    return {"transform": "identity"}


def normalize(_role: str, value: Any, _context: dict[str, Any]) -> Any:
    return value
