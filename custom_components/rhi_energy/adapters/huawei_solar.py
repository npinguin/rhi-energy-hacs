"""Huawei Solar Energy source-role refinements.

Foundation discovers technical candidates mechanically. This adapter only resolves
stable Huawei source-identity families so grid-meter telemetry cannot materialize
as photovoltaic inverter truth. It never inspects HA entity IDs, friendly names,
device names, or Foundation-private state.
"""
from __future__ import annotations

from typing import Any
import re


def _unique_id(candidate: dict[str, Any]) -> str:
    return str((candidate.get("source_identity") or {}).get("unique_id") or "")


_PACK_RE = re.compile(r"_storage_unit_(\d+)_battery_pack_(\d+)_")


def battery_unit_key(candidate: dict[str, Any]) -> str | None:
    """Return stable Huawei battery-pack identity from source unique-id semantics."""
    unique_id = _unique_id(candidate)
    match = _PACK_RE.search(unique_id)
    if match:
        return f"storage_unit_{match.group(1)}:pack_{match.group(2)}"
    return None


def accept_candidate(input_id: str, candidate: dict[str, Any]) -> bool:
    """Refine Huawei source-role families using Foundation-published stable identity."""
    unique_id = _unique_id(candidate)
    if not unique_id:
        return True

    # Huawei exposes inverter and power-meter measurements in one integration.
    # The stable source identity distinguishes the meter family. The HA entity
    # or device display name is deliberately not consulted.
    meter_family = "_power_meter_" in unique_id or "_active_grid_" in unique_id
    grid_accumulator = "_grid_accumulated_" in unique_id or "_grid_exported_" in unique_id

    if input_id in {
        "solar_power",
        "solar_ac_power",
        "solar_ac_frequency",
        "solar_reactive_power",
        "phase_current",
        "phase_voltage_ln",
        "phase_voltage_ll",
    }:
        if meter_family or grid_accumulator:
            return False

    if input_id == "solar_reactive_power":
        return unique_id.endswith("_reactive_power") and not grid_accumulator

    if input_id in {"solar_power", "solar_ac_power"}:
        return unique_id.endswith("_active_power")

    return True


def normalize(role: str, value: Any, _context: dict[str, Any]) -> Any:
    """Huawei measurements already follow Energy's canonical sign conventions."""
    return value
