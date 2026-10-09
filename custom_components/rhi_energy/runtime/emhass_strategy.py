"""Explicit Energy-strategy coverage for native EMHASS 0.18.5.

A cost-minimizing solver is not implicitly equivalent to every Energy product
preference. Hard incompatible policies prevent native planning; softer
preferences remain visible as advisory coverage rather than disappearing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .emhass_native import NativeCapabilityError


@dataclass(frozen=True)
class EmhassStrategyCoverage:
    effective_reserve_pct: float
    mapped_constraints: tuple[str, ...]
    advisory_preferences: tuple[str, ...]
    blockers: tuple[str, ...]


def assess_emhass_strategy(strategy: dict[str, Any]) -> EmhassStrategyCoverage:
    mapped = [
        "site.grid_import_export_limits",
        "battery.per_asset_soc_reserve",
        "battery.per_asset_power_efficiency",
        "flexible.deadline_and_energy_demand",
        "operating_mode.independent_command_policy",
        "pricing.interval_import_and_export_cost",
    ]
    soft = []
    blocking = []
    try:
        reserve = float(strategy.get("battery.reserve_target_pct", 20))
    except (TypeError, ValueError) as exc:
        raise NativeCapabilityError("strategy_reserve_invalid") from exc
    if not 0 <= reserve <= 100:
        raise NativeCapabilityError("strategy_reserve_invalid")
    if strategy.get("resilience.objective") == "resilience_first":
        reserve = max(reserve, 30)
        mapped.append("resilience.first_minimum_30_percent")
    # These are hard per-source restrictions that a single site-wide import
    # limit cannot express. Never lower their meaning to a soft tariff penalty.
    strict_policies = {
        "battery.grid_policy": {"never", "not_applicable", "avoid_or_unavailable"},
        "grid.home_battery_policy": {"never", "not_applicable", "avoid_or_unavailable"},
        "flexible_loads.grid_policy": {"never", "not_applicable", "avoid_or_unavailable"},
        "flexible_loads.solar_policy": {"only"},
        "battery.solar_policy": {"only"},
    }
    for key, disallowed in strict_policies.items():
        value = strategy.get(key)
        if value in disallowed:
            blocking.append(f"native_missing_hard_policy:{key}={value}")
    # The selected solver optimizes economics subject to physical constraints.
    # It cannot faithfully reproduce qualitative RHI preference orderings.
    qualitative = (
        "home.primary_objective", "battery.objective",
        "solar.surplus_objective", "flexible_loads.objective",
        "battery.grid_policy", "battery.solar_policy",
        "flexible_loads.grid_policy", "flexible_loads.solar_policy",
    )
    for key in qualitative:
        value = strategy.get(key)
        if value is not None:
            soft.append(f"native_cost_objective_may_differ:{key}={value}")
    return EmhassStrategyCoverage(
        effective_reserve_pct=reserve,
        mapped_constraints=tuple(mapped),
        advisory_preferences=tuple(soft),
        blockers=tuple(sorted(set(blocking))),
    )
