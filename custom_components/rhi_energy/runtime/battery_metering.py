"""Metering readout of Energy-authored gross physical battery directions.

Battery net signed power is NOT a substitute. Opposing physical batteries may
charge and discharge simultaneously with zero net power. Unknown/stale/conflicting
direction measurements must remain unknown, not be back-calculated from net.
"""
from __future__ import annotations

from math import isfinite
from typing import Any


def battery_gross_metering_powers(facts: dict[str, Any]) -> tuple[float | None, float | None]:
    charge = facts.get("battery.charge_power_kw")
    discharge = facts.get("battery.discharge_power_kw")
    for value in (charge, discharge):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, None
        if not isfinite(value) or value < 0:
            return None, None
    return float(charge), float(discharge)


def qualified_battery_balance_powers(
    facts: dict[str, Any],
    *,
    net_power_kw: float | None,
    battery_present: bool,
    tolerance_kw: float = 0.10,
) -> tuple[float | None, float | None, str | None]:
    """One strict gross-direction authority for canonical site/home balance.

    A physically absent battery is a proven zero. A configured battery with
    incomplete, nonphysical or contradictory gross telemetry is UNKNOWN; its
    signed net must never be split to invent internal charging/discharging.
    """
    if not battery_present:
        return 0.0, 0.0, None
    charge, discharge = battery_gross_metering_powers(facts)
    if charge is None or discharge is None or net_power_kw is None:
        return None, None, "battery_balance:gross_directions_unavailable"
    if abs(discharge - charge - net_power_kw) > tolerance_kw:
        return None, None, "battery_balance:gross_net_disagreement"
    return charge, discharge, None
