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


def validated_battery_available_kwh(
    raw_capacity: Any, raw_soc: Any,
) -> tuple[float | None, float | None, bool]:
    """Qualify physical rated kWh and SoC without guessing missing units."""
    def finite(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value) if isfinite(value) else None

    capacity = finite(raw_capacity)
    invalid_capacity = raw_capacity is not None and (
        capacity is None or capacity < 0
    )
    if capacity is None or capacity < 0:
        return None, None, invalid_capacity
    soc = finite(raw_soc)
    if soc is None or not 0 <= soc <= 100:
        return capacity, None, False
    return capacity, round(capacity * soc / 100, 4), False


def apply_battery_capacity_facts(
    props: dict[str, dict[str, Any]], facts: dict[str, Any],
    issues: list[str], asset_id: str,
) -> None:
    """Publish physically valid capacity/usable kWh for one accepted battery."""
    capacity_key = str((props.get("battery.capacity_kwh") or {}).get("fact_key") or "")
    soc_key = str((props.get("battery.soc_pct") or {}).get("fact_key") or "")
    available_key = str((props.get("battery.available_kwh") or {}).get("fact_key") or "")
    if not capacity_key and not available_key:
        return
    capacity, available, invalid = validated_battery_available_kwh(
        facts.get(capacity_key), facts.get(soc_key),
    )
    if capacity_key:
        facts[capacity_key] = capacity
    if invalid:
        issues.append(f"battery:{asset_id}:invalid_rated_capacity_source")
    if available_key:
        facts[available_key] = available


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
