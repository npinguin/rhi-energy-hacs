"""RHI-owned solver parameter resolution; no duplicate optimizer preferences.

Every physical bound comes from a canonical accepted source/capability.
Unknown is not zero and is never replaced by a guessed EMHASS default.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


class MissingNativeCapability(ValueError):
    pass


def required_number(value: Any, name: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < minimum:
        raise MissingNativeCapability("canonical_capability_missing:" + name)
    return float(value)


def battery_configuration_from_canonical(
    battery_units: list[dict[str, Any]],
    *,
    strategy_reserve_pct: float,
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for unit in battery_units:
        name = str(unit.get("asset_id") or "")
        if not name or name in result:
            raise MissingNativeCapability("canonical_battery_identity_invalid")
        charge = unit.get("max_charge_power_kw")
        discharge = unit.get("max_discharge_power_kw")
        if charge is None:
            charge = unit.get("charge_limit_kw")
        if discharge is None:
            discharge = unit.get("discharge_limit_kw")
        reserve = unit.get("reserve_soc_pct")
        if reserve is None:
            reserve = strategy_reserve_pct
        result[name] = {
            "soc_min_pct": max(
                required_number(reserve, name + ":reserve_soc_pct"),
                required_number(strategy_reserve_pct, "strategy:battery_reserve"),
            ),
            "soc_max_pct": required_number(unit.get("soc_max_pct"), name + ":soc_max_pct"),
            "charge_max_kw": required_number(charge, name + ":charge_limit_kw"),
            "discharge_max_kw": required_number(discharge, name + ":discharge_limit_kw"),
            "charge_efficiency": required_number(unit.get("charge_efficiency"), name + ":charge_efficiency"),
            "discharge_efficiency": required_number(unit.get("discharge_efficiency"), name + ":discharge_efficiency"),
        }
    return result


def canonical_site_limits(facts: Mapping[str, Any]) -> tuple[float, float]:
    return (
        required_number(facts.get("grid.import_capacity_limit_kw"), "grid.import_capacity_limit_kw"),
        required_number(facts.get("grid.export_capacity_limit_kw"), "grid.export_capacity_limit_kw"),
    )


def canonical_export_compensation(facts: Mapping[str, Any], settings: dict[str, Any]) -> float:
    from .canonical_semantics import pricing_properties
    rows = pricing_properties(dict(facts), settings)
    for row in rows:
        if row.get("key") == "pricing.export_compensation_current_eur_kwh":
            return required_number(row.get("value"), "pricing.export_compensation", minimum=-10)
    raise MissingNativeCapability("canonical_capability_missing:pricing.export_compensation")
