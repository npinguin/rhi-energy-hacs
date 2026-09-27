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


def normalize(role: str, value: Any, _context: dict[str, Any]) -> Any:
    if value is None:
        return None
    # RHI canonical stationary-battery power is positive while discharging and
    # negative while charging. Runtime qualification verifies the sonnen sign.
    if role == "battery.power_kw":
        return -float(value)
    # RHI grid net power is positive import / negative export; passthrough until
    # House-4 runtime qualification verifies the provider sign convention.
    return value
