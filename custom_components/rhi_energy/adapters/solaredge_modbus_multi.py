"""SolarEdge Modbus Multi Energy value conventions."""
from __future__ import annotations

import re
from typing import Any


def accept_candidate(input_id: str, candidate: dict[str, Any]) -> bool:
    """Refine native Bx/M1 siblings after Foundation's mechanical match."""
    unique_id = str((candidate.get("source_identity") or {}).get("unique_id") or "")
    if not unique_id:
        return True
    suffixes = {
        "battery_unit_power": r"_B[1-4]_dc_power$",
        "battery_status": r"_B[1-4]_status$",
        "grid_net_power": r"_M1_ac_power$",
        "grid_import_energy": r"_M1_imported_kwh$",
        "grid_export_energy": r"_M1_exported_kwh$",
        "grid_phase_power": r"_M1_ac_power_[abc]$",
    }
    if input_id in suffixes:
        family_marker = "_B" if input_id.startswith("battery_") else "_M1_"
        return family_marker not in unique_id or re.search(suffixes[input_id], unique_id) is not None
    if input_id == "solar_power":
        return re.search(r"_B[1-4]_", unique_id) is None and not unique_id.endswith("_inverted")
    if input_id == "inverter_status":
        return unique_id.endswith("_status") and re.search(r"_B[1-4]_", unique_id) is None
    return True


def normalize(role: str, value: Any, context: dict[str, Any]) -> Any:
    if value is None:
        return None
    if role == "battery.power_kw":
        # Integration is positive charging; Energy is positive discharge.
        return -float(value)
    if role == "grid.net_power_kw":
        # Integration direction is opposite to Energy import-positive convention.
        return -float(value)
    if role == "solar.power_kw":
        # Some SolarEdge Modbus Multi inverter power surfaces include battery flow.
        # When a linked battery is proven, unknown battery flow is not guessed as zero.
        linked = context.get("linked_battery_power_kw")
        if linked is None and context.get("linked_battery_present"):
            return None
        correction = -float(linked) if linked is not None else 0.0
        return max(0.0, float(value) + correction)
    return value
