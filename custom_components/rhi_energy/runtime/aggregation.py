"""Change-scoped Energy aggregate evaluation over prebound structural indexes."""
from __future__ import annotations

from typing import Any

from .canonical_semantics import (
    aggregate_battery_power,
    aggregate_battery_soc,
    battery_state_from_power,
    complete_numeric_sum,
)
from .solar_accounting import aggregate_solar_system


def aggregate_objects(
    assets_by_class: dict[str, tuple[dict[str, Any], ...]],
    children_by_parent_class: dict[tuple[str, str], tuple[dict[str, Any], ...]],
    facts: dict[str, Any],
    issues: list[str],
    *,
    affected_asset_ids: set[str] | None = None,
) -> None:
    """Refresh only aggregates whose system or children are in the changed scope."""

    def children(parent_id: str, object_class: str) -> list[dict[str, Any]]:
        return list(children_by_parent_class.get((str(parent_id), str(object_class)), ()))

    def affected(system_id: str, rows: list[dict[str, Any]]) -> bool:
        return (
            affected_asset_ids is None
            or system_id in affected_asset_ids
            or any(str(row.get("asset_id") or "") in affected_asset_ids for row in rows)
        )

    for system in assets_by_class.get("battery_system", ()):
        sid = str(system.get("asset_id") or "")
        units = children(sid, "battery")
        if not affected(sid, units):
            continue
        pvals = [facts.get(f"{u.get('asset_id')}.power_kw") for u in units]
        cvals = [facts.get(f"{u.get('asset_id')}.capacity_kwh") for u in units]
        avals = [facts.get(f"{u.get('asset_id')}.available_kwh") for u in units]
        socvals = [facts.get(f"{u.get('asset_id')}.soc_pct") for u in units]
        svals = [facts.get(f"{u.get('asset_id')}.status") for u in units]
        direct_power = facts.get(f"{sid}.power_kw")
        direct_capacity = facts.get(f"{sid}.capacity_kwh")
        direct_soc = facts.get(f"{sid}.soc_pct")
        direct_status = facts.get(f"{sid}.status")
        child_power = complete_numeric_sum(pvals, expected_count=len(units))
        child_capacity = complete_numeric_sum(cvals, expected_count=len(units))
        child_available = complete_numeric_sum(avals, expected_count=len(units))
        facts[f"{sid}.power_kw"] = aggregate_battery_power(
            pvals, direct_power, unit_count=len(units)
        )
        if (
            units
            and child_power is not None
            and isinstance(direct_power, (int, float))
            and abs(float(direct_power) - float(child_power)) > 0.10
        ):
            issues.append(f"battery_system:{sid}:direct_power_disagrees_with_child_power")
        facts[f"{sid}.capacity_kwh"] = (
            child_capacity if child_capacity is not None else direct_capacity
        )
        capacity = facts[f"{sid}.capacity_kwh"]
        aggregate_soc = aggregate_battery_soc(child_capacity, child_available, socvals)
        facts[f"{sid}.soc_pct"] = aggregate_soc if aggregate_soc is not None else direct_soc
        facts[f"{sid}.available_kwh"] = (
            child_available
            if child_available is not None
            else round(float(capacity) * float(facts[f"{sid}.soc_pct"]) / 100.0, 6)
            if isinstance(capacity, (int, float))
            and isinstance(facts[f"{sid}.soc_pct"], (int, float))
            else None
        )
        if (
            aggregate_soc is not None
            and isinstance(direct_soc, (int, float))
            and abs(float(direct_soc) - float(aggregate_soc)) > 1.0
        ):
            issues.append(f"battery_system:{sid}:direct_soc_disagrees_with_child_energy")
        facts[f"{sid}.status"] = (
            direct_status
            if direct_status is not None
            else next(iter(set(svals)))
            if units and all(value is not None for value in svals) and len(set(svals)) == 1
            else "mixed"
            if units and all(value is not None for value in svals)
            else None
        )
        facts["battery.power_kw"] = facts[f"{sid}.power_kw"]
        facts["battery.capacity_kwh"] = facts[f"{sid}.capacity_kwh"]
        facts["battery.available_kwh"] = facts[f"{sid}.available_kwh"]
        facts["battery.soc_pct"] = facts[f"{sid}.soc_pct"]
        facts["battery.status"] = facts[f"{sid}.status"]
        facts["battery.state"] = battery_state_from_power(facts[f"{sid}.power_kw"])
        facts["battery_system.source_id"] = sid
        if units and facts[f"{sid}.power_kw"] is None:
            issues.append(f"battery_system:{sid}:power_aggregate_incomplete")
        if units and (
            facts[f"{sid}.capacity_kwh"] is None
            or facts[f"{sid}.available_kwh"] is None
        ):
            issues.append(f"battery_system:{sid}:energy_aggregate_incomplete")

    for system in assets_by_class.get("solar_production", ()):
        sid = str(system.get("asset_id") or "")
        inverters = children(sid, "solar_inverter")
        sources = children(sid, "solar_source")
        if not affected(sid, inverters + sources):
            continue
        issues.extend(
            aggregate_solar_system(
                system, inverters, sources, facts, complete_numeric_sum
            )
        )

    meters = list(assets_by_class.get("gas_meter", ()))
    if affected_asset_ids is None or any(
        str(row.get("asset_id") or "") in affected_asset_ids for row in meters
    ):
        gas_values = [facts.get(f"{row.get('asset_id')}.total_m3") for row in meters]
        facts["gas.total_m3"] = complete_numeric_sum(
            gas_values, expected_count=len(meters)
        )
        facts["gas.total"] = facts["gas.total_m3"]
        if meters and any(value is None for value in gas_values):
            issues.append(
                "gas_meter:aggregate_incomplete:"
                f"{sum(value is None for value in gas_values)}_of_{len(meters)}_unavailable"
            )

    optimizers = list(assets_by_class.get("solar_optimizer", ()))
    if optimizers and (
        affected_asset_ids is None
        or any(str(row.get("asset_id") or "") in affected_asset_ids for row in optimizers)
    ):
        known = sum(
            facts.get(f"{row.get('asset_id')}.power_w") is not None
            for row in optimizers
        )
        facts["solar_optimizer.count"] = len(optimizers)
        facts["solar_optimizer.health"] = (
            "OK" if known == len(optimizers) else "DEGRADED"
        )
