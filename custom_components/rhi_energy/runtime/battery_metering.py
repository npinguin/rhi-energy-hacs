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
