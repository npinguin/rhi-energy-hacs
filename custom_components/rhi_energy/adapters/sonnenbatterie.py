"""sonnenBatterie Energy value conventions and candidate refinement.

Foundation owns discovery. This adapter only refines already-selected candidates using
stable provider identity and normalizes provider value conventions.
"""
from __future__ import annotations

from typing import Any


_PRIMARY_WRITE_INPUTS = {
    "reserve_write_surface",
    "storage_charge_limit_write",
    "storage_discharge_limit_write",
    "storage_control_mode_write",
}


def accept_candidate(input_id: str, candidate: dict[str, Any]) -> bool:
    """Drop duplicate technical write entities, never by HA display/entity name."""
    if input_id not in _PRIMARY_WRITE_INPUTS:
        return True
    source = candidate.get("source_identity") or {}
    unique_id = str(source.get("unique_id") or "")
    return unique_id.startswith("sonnenbatterie.")


def normalization_semantics(role: str) -> dict[str, str]:
    """Describe sonnen source semantics proven by directional runtime evidence."""
    if role == "battery.power_kw":
        return {
            "source_semantics": "signed battery in/out power",
            "source_sign_convention": "positive=discharge, negative=charge",
            "canonical_sign_convention": "positive=discharge, negative=charge",
            "transform": "identity",
        }
    if role == "grid.net_power_kw":
        return {
            "source_semantics": "signed grid in/out power",
            "source_sign_convention": "positive=import, negative=export",
            "canonical_sign_convention": "positive=import, negative=export",
            "transform": "identity",
        }
    return {"transform": "identity"}


def normalize(role: str, value: Any, _context: dict[str, Any]) -> Any:
    if value is None:
        return None
    # House qualification shows state_battery_inout is already positive while
    # discharging: measured_charge=0, measured_discharge>0 and status=discharging.
    # Do not invert it a second time.
    if role == "battery.power_kw":
        return float(value)
    return value
