"""SolarEdge Optimizers Energy semantic candidate refinement.

Foundation publishes technical candidates. Energy distinguishes site summaries, zone
summaries and leaf optimizers using stable integration entity/unique-id shapes only;
display names are never semantic evidence.
"""
from __future__ import annotations

from typing import Any
import re


def _token(candidate: dict[str, Any]) -> str:
    source = candidate.get("source_identity") or {}
    return str(source.get("unique_id") or "").lower()


def accept_candidate(input_id: str, candidate: dict[str, Any]) -> bool:
    token = _token(candidate)
    if not token:
        return True
    rules = {
        "optimizer_voltage": ("optimizer_voltage_",),
        "panel_voltage": ("sensor.voltage_", "_voltage_"),
        "optimizer_current": ("sensor.current_", "_current_"),
        "optimizer_temperature": ("sensor.temperature_", "_temperature_"),
        "optimizer_tilt": ("sensor.tilt_", "_tilt_"),
        "optimizer_azimuth": ("sensor.azimuth_", "_azimuth_"),
        "zone_voltage_average": ("voltage_average_",),
        "zone_current_average": ("current_average_",),
        "zone_child_count": ("child_count_",),
        "zone_max_active_power": ("max_active_power_",),
        "optimizer_status": ("status_",),
        "optimizer_last_measurement": ("last_measurement_",),
        "site_peak_power": ("peak_power_",),
        "site_installation_date": ("installation_date_",),
        "site_last_polled": ("last_polled",),
        "site_inverter_count": ("inverter_count_",),
        "site_obtained_from": ("obtained_from",),
    }
    expected = rules.get(input_id)
    if expected is None:
        return True
    if input_id == "panel_voltage" and "voltage_average_" in token:
        return False
    if input_id == "optimizer_current" and "current_average_" in token:
        return False
    if input_id == "optimizer_status" and "status_vendor" in token:
        return False
    return any(value in token for value in expected)


def normalize(_role: str, value: Any, _context: dict[str, Any]) -> Any:
    return value


_TOPOLOGY_SUFFIX = re.compile(
    r"(?:^|[._])(?:power|voltage_average|current_average|child_count|max_active_power|peak_power|installation_date|last_polled|inverter_count|obtained_from)_([0-9]+(?:_[0-9]+)*)$"
)


def topology_key(row: dict[str, Any]) -> str | None:
    """Extract the integration's stable numeric topology path from source identity.

    SolarEdge Optimizers publishes site/zone/leaf identity in provider-owned unique-id
    suffixes (for example power_1_2_21 and voltage_average_1_2). User-renamable
    entity ids and display names are never semantic evidence.
    """
    for value in (row.get("source_unique_id"), row.get("unique_id")):
        match = _TOPOLOGY_SUFFIX.search(str(value or "").lower())
        if match:
            return match.group(1)
    return None
