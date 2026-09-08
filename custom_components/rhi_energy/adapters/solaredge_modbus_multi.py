"""SolarEdge Modbus Multi Energy value conventions."""
from __future__ import annotations

from typing import Any


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
