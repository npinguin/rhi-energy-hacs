"""Pure product semantics and R1.89.45 public-contract projection helpers.

This module deliberately has no Home Assistant imports so all product semantics
can be contract-tested without a running HA instance.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math
from typing import Any, Iterable

AVAILABLE = "AVAILABLE"
CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
UNAVAILABLE = "UNAVAILABLE"
UNSUPPORTED = "UNSUPPORTED"
STALE = "STALE"
RESET_PENDING = "RESET_PENDING"
INCOMPLETE = "INCOMPLETE"
INVALID = "INVALID"
PENDING = "PENDING"




def optional_physical_input(value: Any, *, concept_absent: bool) -> float | None:
    """Map a physically absent optional concept to zero, never an unavailable one."""
    numeric = number(value)
    if numeric is not None:
        return numeric
    return 0.0 if concept_absent else None


def complete_numeric_sum(values: Iterable[Any], *, expected_count: int) -> float | None:
    """Aggregate only complete participating evidence; partial truth stays unknown."""
    rows = [number(value) for value in values]
    if expected_count <= 0 or len(rows) != expected_count or any(value is None for value in rows):
        return None
    return round(sum(float(value) for value in rows if value is not None), 6)

def jdump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=False, default=str)


def jload(value: Any, default: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return deepcopy(default)
    return deepcopy(value) if value is not None else deepcopy(default)


def number(value: Any) -> float | None:
    try:
        if value is None or str(value).lower() in {"unknown", "unavailable", "none", ""}:
            return None
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None



def command_state_key(command_id: str, target_asset_id: str | None = None, period_id: str | None = None) -> str:
    return f"{command_id}:{period_id or ''}:{target_asset_id or ''}"

def prop(
    asset_id: str,
    key: str,
    value: Any,
    unit: str = "",
    *,
    availability: str | None = None,
    editable: bool = False,
    editor: str | None = None,
    constraints: dict[str, Any] | None = None,
    operation_id: str | None = None,
    reason_code: str | None = None,
    reason_text: str | None = None,
    source_type: str = "canonical_runtime",
    quality: str = "authoritative",
    group: str | None = None,
    choices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if availability is None:
        availability = AVAILABLE if value is not None else UNAVAILABLE
    write = {
        "supported": editable,
        "operation_id": operation_id if editable else None,
        "operation_kind": "property_write" if editable else None,
        "service": "script.energy_write_public_property" if editable else None,
        "data": {"property_id": key} if editable else {},
        "value_parameter": "value" if editable else None,
        "readback_property": key,
    }
    row = {
        "asset_id": asset_id,
        "property_id": key,
        "key": key,
        "value": value,
        "unit": unit,
        "availability": availability,
        "editable": editable,
        "editor": editor,
        "constraints": constraints,
        "write": write,
        "write_supported": editable,
        "write_interface": "operation" if editable else None,
        "write_state": "IDLE" if editable else "READ_ONLY",
        "reason_code": reason_code,
        "reason_text": reason_text,
        "readback_property": key,
        "quality": quality,
        "source_type": source_type,
        "health": "OK" if availability == AVAILABLE else availability,
        "group": group,
    }
    if choices is not None:
        row["choices"] = choices
    return row


def by_key(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["key"]): row for row in rows if isinstance(row, dict) and row.get("key")}


def split_battery_power(power_kw: float | None) -> tuple[float | None, float | None]:
    if power_kw is None:
        return None, None
    return max(0.0, -power_kw), max(0.0, power_kw)


def battery_state_from_power(power_kw: float | None, *, deadband_kw: float = 0.05) -> str | None:
    """Return canonical battery flow state from signed canonical battery power."""
    if power_kw is None:
        return None
    if power_kw > deadband_kw:
        return "discharging"
    if power_kw < -deadband_kw:
        return "charging"
    return "idle"


def grid_flow_direction(net_power_kw: float | None, *, deadband_kw: float = 0.05) -> str | None:
    """Return canonical site-boundary direction; positive grid power is import."""
    if net_power_kw is None:
        return None
    if net_power_kw > deadband_kw:
        return "importing"
    if net_power_kw < -deadband_kw:
        return "exporting"
    return "balanced"


def derive_consumption(solar_kw: float | None, grid_net_kw: float | None, battery_kw: float | None, max_home_kw: float | None = None) -> dict[str, Any]:
    """Derive canonical Site Consumption from the site-boundary energy balance.

    Canonical semantics:
      supply = solar + grid_import + battery_discharge
      site_consumption = home_consumption + flexible_loads + battery_charge
      supply = site_consumption + grid_export

    Battery charge is therefore *inside* Site Consumption. Battery discharge is a
    supply source and may serve local Site Consumption and/or Grid Export.
    """
    if solar_kw is None or grid_net_kw is None or battery_kw is None:
        return {"power_kw": None, "health": "UNAVAILABLE", "reason": "required_energy_balance_input_missing", "raw_balance_kw": None}
    _, battery_discharge = split_battery_power(float(battery_kw))
    raw = float(solar_kw) + float(grid_net_kw) + float(battery_discharge or 0.0)
    deadband = 0.08
    if raw < -deadband:
        return {"power_kw": None, "health": "DEGRADED", "reason": "physical_balance_inconsistent_negative_balance_above_deadband", "raw_balance_kw": round(raw, 3)}
    value = 0.0 if raw < 0 else raw
    if max_home_kw is not None and value > max_home_kw:
        return {"power_kw": None, "health": "DEGRADED", "reason": "implausible_site_consumption_above_configured_site_limit", "raw_balance_kw": round(raw, 3)}
    return {"power_kw": round(value, 3), "health": "OK", "reason": "derived_from_site_boundary_energy_balance", "raw_balance_kw": round(raw, 3)}


def derive_home_consumption(
    site_consumption_kw: float | None,
    flexible_loads_kw: float | None,
    battery_kw: float | None,
    *,
    deadband_kw: float = 0.08,
) -> dict[str, Any]:
    """Derive non-flexible Home Consumption from canonical internal sinks."""
    if site_consumption_kw is None or flexible_loads_kw is None or battery_kw is None:
        return {
            "power_kw": None,
            "health": "UNAVAILABLE",
            "reason": "required_internal_consumption_input_missing",
            "raw_residual_kw": None,
        }
    battery_charge, _ = split_battery_power(float(battery_kw))
    raw = (
        float(site_consumption_kw)
        - float(flexible_loads_kw)
        - float(battery_charge or 0.0)
    )
    if raw < -deadband_kw:
        return {
            "power_kw": None,
            "health": "DEGRADED",
            "reason": "internal_sinks_exceed_site_consumption",
            "raw_residual_kw": round(raw, 3),
        }
    return {
        "power_kw": round(max(0.0, raw), 3),
        "health": "OK",
        "reason": "site_minus_flexible_minus_battery_charge",
        "raw_residual_kw": round(raw, 3),
    }


def overview_snapshot(facts: dict[str, Any], demand_breakdown: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build the exact R1.89.45 Overview snapshot semantics.

    Status and primary metric are intentionally inseparable and backend-owned.
    Missing core facts remain unavailable; they are never coerced to zero.
    """
    solar = number(facts.get("solar.power_kw"))
    site = number(facts.get("site_consumption.power_kw"))
    home = number(facts.get("home_consumption.power_kw"))
    gi = number(facts.get("grid_import.power_kw"))
    ge = number(facts.get("grid_export.power_kw"))
    bp = number(facts.get("battery.power_kw"))
    soc = number(facts.get("battery.soc_pct"))
    charge, discharge = split_battery_power(bp)
    supply_total = (
        solar + gi + (discharge or 0.0)
        if all(v is not None for v in (solar, gi, discharge))
        else None
    )
    consumption_total = (
        site + ge
        if site is not None and ge is not None
        else None
    )
    balance_delta = (
        round(supply_total - consumption_total, 6)
        if supply_total is not None and consumption_total is not None
        else None
    )
    complete = all(v is not None for v in (solar, site, gi, ge))
    if not complete:
        code, title, primary, key = "unavailable", "Energy data unavailable", None, "site_consumption.power_kw"
    elif ge > 0.05:
        code, title, primary, key = "exporting", "Exporting surplus", site, "site_consumption.power_kw"
    elif gi > 0.05:
        code, title, primary, key = "importing", "Importing from grid", site, "site_consumption.power_kw"
    elif discharge is not None and discharge > 0.05:
        code, title, primary, key = "battery_support", "Battery supporting site", site, "site_consumption.power_kw"
    elif solar > 0.05:
        code, title, primary, key = "self_powered", "Solar powering site", site, "site_consumption.power_kw"
    else:
        code, title, primary, key = "idle", "Energy balanced", site, "site_consumption.power_kw"
    return {
        "schema": "energy_overview_snapshot_v2",
        "status": {"code": code, "title": title, "available": complete},
        "primary_metric": {"value": round(primary, 3) if primary is not None else None, "unit": "kW", "property_key": key},
        "summary": {
            "solar_power_kw": round(solar, 3) if solar is not None else None,
            "site_consumption_power_kw": round(site, 3) if site is not None else None,
            "home_consumption_power_kw": round(home, 3) if home is not None else None,
            "home_power_kw": round(home, 3) if home is not None else None,
            "grid_import_power_kw": round(gi, 3) if gi is not None else None,
            "grid_export_power_kw": round(ge, 3) if ge is not None else None,
            "battery_charge_power_kw": round(charge, 3) if charge is not None else None,
            "battery_discharge_power_kw": round(discharge, 3) if discharge is not None else None,
            "battery_soc_pct": round(soc, 1) if soc is not None else None,
            "supply_total_power_kw": round(supply_total, 3) if supply_total is not None else None,
            "consumption_total_power_kw": round(consumption_total, 3) if consumption_total is not None else None,
            "energy_balance_delta_kw": balance_delta,
        },
        "flow": {
            "sources": [
                {"participant_id": "solar", "power_kw": round(solar, 3) if solar is not None else None},
                {"participant_id": "battery", "power_kw": round(discharge, 3) if discharge is not None else None},
                {"participant_id": "grid", "direction": "import", "power_kw": round(gi, 3) if gi is not None else None},
            ],
            "demands": deepcopy(demand_breakdown or []),
        },
        "ownership": {
            "status_and_primary_metric": "sensor.energy_overview_experience",
            "physical_facts": "domain_property_indexes",
            "ux_recalculation_allowed": False,
        },
        "optional_battery_flow_available": bp is not None,
        "complete": complete,
    }


def _period_label(period_id: str) -> str:
    return {"hour": "This hour", "today": "Today", "week": "This week", "month": "This month", "year": "This year"}.get(period_id, period_id)


def metering_rows(metering: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for pid in ("hour", "today", "week", "month", "year"):
        bucket = deepcopy((metering.get("periods") or {}).get(pid) or {})
        quality = str(bucket.get("quality") or "UNKNOWN")
        measured_fields = (
            "solar_kwh", "grid_import_kwh", "grid_export_kwh",
            "site_consumption_kwh", "home_consumption_kwh",
            "battery_charge_kwh", "battery_discharge_kwh",
            "flexible_loads_energy_in_kwh",
        )
        # Availability answers whether this period has usable measurements.
        # Quality answers whether the period is complete. Keep those semantics
        # separate: PARTIAL evidence is still available, while an empty period
        # never becomes available merely because a stale quality flag says OK.
        has_measurement = any(number(bucket.get(key)) is not None for key in measured_fields)
        availability = AVAILABLE if has_measurement else UNAVAILABLE
        rows.append({
            "period_id": pid,
            "label": _period_label(pid),
            "availability": availability,
            "quality": quality,
            "solar_kwh": bucket.get("solar_kwh"),
            "grid_import_kwh": bucket.get("grid_import_kwh"),
            "grid_export_kwh": bucket.get("grid_export_kwh"),
            "site_consumption_kwh": bucket.get("site_consumption_kwh"),
            "home_consumption_kwh": bucket.get("home_consumption_kwh"),
            "battery_charge_kwh": bucket.get("battery_charge_kwh"),
            "battery_discharge_kwh": bucket.get("battery_discharge_kwh"),
            "flexible_loads_energy_in_kwh": bucket.get("flexible_loads_energy_in_kwh"),
            "flexible_assets_kwh": deepcopy(bucket.get("flexible_assets_kwh") or {}),
            "import_cost_eur": bucket.get("import_cost_eur"),
            "export_revenue_eur": bucket.get("export_revenue_eur"),
            "financial_quality": deepcopy(bucket.get("financial_quality") or {}),
            "baseline_reset_required": False,
            "can_be_used_for_remaining": quality == "OK" and availability == AVAILABLE,
            "remaining_use_policy": "allowed" if quality == "OK" and availability == AVAILABLE else "not_available",
            "baseline_reset_action_ref": f"energy.command.reset_metering_baseline.{pid}.metering",
            "field_quality": deepcopy(bucket.get("field_quality") or {}),
            "field_coverage_seconds": deepcopy(bucket.get("field_coverage_seconds") or {}),
        })
    return rows


def default_settings() -> dict[str, Any]:
    return {
        "metering_selected_period": "today",
        "pricing": {
            "spot_fallback_eur_kwh": None,
            "import_network_eur_kwh": None,
            "import_levies_eur_kwh": None,
            "import_vat_pct": None,
            "export_fee_eur_kwh": None,
        },
        "strategy": {
            "energy.automation_mode": "advice",
            "energy.operating_mode": "advice",
            "home.primary_objective": "balanced",
            "battery.objective": "balanced",
            "battery.grid_policy": "cheap_only",
            "battery.solar_policy": "prefer",
            "battery.battery_policy": "protect_reserve",
            "battery.surplus_policy": "absorb",
            "battery.reserve_target_pct": 20.0,
            "solar.surplus_objective": "self_consumption",
            "solar.grid_policy": "never",
            "solar.solar_policy": "primary",
            "solar.battery_policy": "allow",
            "solar.surplus_policy": "prefer",
            "grid.home_battery_policy": "cheap_only",
            "grid.flexible_load_policy": "cheap_only",
            "flexible_loads.objective": "balanced",
            "flexible_loads.grid_policy": "cheap_only",
            "flexible_loads.solar_policy": "prefer",
            "flexible_loads.battery_policy": "minimum_power_bridge",
            "flexible_loads.surplus_policy": "prefer",
            "resilience.objective": "resilience_first",
            "resilience.grid_policy": "if_needed_for_minimum",
            "resilience.battery_policy": "protect_reserve",
        },
        "planning": {
            "explicit_baseload_fallback_kw": None,
            "solar_window_start_hour": 7,
            "solar_window_end_hour": 20,
        },
        "sources": {
            "grid_connection": "auto",
            "solar_production": "auto",
            "solar_forecast": "auto",
            "price_source": "auto",
        },
        "holds": {},
    }


_OBJECTIVES = ("balanced","deadline_first","cheapest","comfort_first","self_consumption","resilience_first")
_GRID_POLICIES = ("never","cheap_only","if_needed_for_minimum","if_needed_for_preferred","always_allowed","not_applicable","avoid_or_unavailable")
_SOLAR_POLICIES = ("only","prefer","allow","absorb","primary")
_BATTERY_POLICIES = ("never","avoid","avoid_unless_resilience","allow","protect_reserve","optional_buffer","minimum_power_bridge")
_SURPLUS_POLICIES = ("avoid","allow","prefer","absorb")
_MODES = ("automatic","advice","disabled")


def _choice_rows(values: tuple[str, ...]) -> list[dict[str, str]]:
    return [{"value":x,"label":x.replace("_"," ").title()} for x in values]


def _strategy_select(settings: dict[str, Any], key: str, allowed: tuple[str, ...], group: str) -> dict[str, Any]:
    value=(settings.get("strategy") or {}).get(key)
    return prop(group, key, value, editable=True, editor="select", operation_id="energy.strategy.set_property", choices=_choice_rows(allowed), constraints={"allowed":list(allowed)}, group=group)


def strategy_properties(settings: dict[str, Any]) -> list[dict[str, Any]]:
    s=settings.get("strategy") or {}
    rows=[
        _strategy_select(settings,"energy.automation_mode",_MODES,"home"),
        _strategy_select(settings,"home.primary_objective",_OBJECTIVES,"home"),
        _strategy_select(settings,"battery.objective",_OBJECTIVES,"battery"),
        _strategy_select(settings,"battery.grid_policy",_GRID_POLICIES,"battery"),
        _strategy_select(settings,"battery.solar_policy",_SOLAR_POLICIES,"battery"),
        _strategy_select(settings,"battery.battery_policy",_BATTERY_POLICIES,"battery"),
        _strategy_select(settings,"battery.surplus_policy",_SURPLUS_POLICIES,"battery"),
        prop("battery","battery.reserve_target_pct",number(s.get("battery.reserve_target_pct")),"%",editable=True,editor="slider",operation_id="energy.strategy.set_property",constraints={"min":5,"max":80,"step":1},group="battery"),
        _strategy_select(settings,"solar.surplus_objective",_OBJECTIVES,"solar"),
        _strategy_select(settings,"solar.grid_policy",_GRID_POLICIES,"solar"),
        _strategy_select(settings,"solar.solar_policy",_SOLAR_POLICIES,"solar"),
        _strategy_select(settings,"solar.battery_policy",_BATTERY_POLICIES,"solar"),
        _strategy_select(settings,"solar.surplus_policy",_SURPLUS_POLICIES,"solar"),
        _strategy_select(settings,"grid.home_battery_policy",_GRID_POLICIES,"grid"),
        _strategy_select(settings,"grid.flexible_load_policy",_GRID_POLICIES,"grid"),
        _strategy_select(settings,"flexible_loads.objective",_OBJECTIVES,"flexible_loads"),
        _strategy_select(settings,"flexible_loads.grid_policy",_GRID_POLICIES,"flexible_loads"),
        _strategy_select(settings,"flexible_loads.solar_policy",_SOLAR_POLICIES,"flexible_loads"),
        _strategy_select(settings,"flexible_loads.battery_policy",_BATTERY_POLICIES,"flexible_loads"),
        _strategy_select(settings,"flexible_loads.surplus_policy",_SURPLUS_POLICIES,"flexible_loads"),
        _strategy_select(settings,"resilience.objective",_OBJECTIVES,"resilience"),
        _strategy_select(settings,"resilience.grid_policy",_GRID_POLICIES,"resilience"),
        _strategy_select(settings,"resilience.battery_policy",_BATTERY_POLICIES,"resilience"),
    ]
    # Additive V2 alias; old UX continues using energy.automation_mode.
    rows.append(_strategy_select(settings,"energy.operating_mode",_MODES,"home"))
    return rows

def pricing_properties(facts: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = settings.get("pricing") or {}
    import_live = number(facts.get("pricing.import_price_current_eur_kwh"))
    if import_live is None:
        import_live = number(facts.get("pricing.spot_eur_kwh"))
    spot_fallback = number(cfg.get("spot_fallback_eur_kwh"))
    import_market = import_live if import_live is not None else spot_fallback
    import_market_av = AVAILABLE if import_market is not None else CONFIGURATION_REQUIRED

    export_live = number(facts.get("pricing.export_price_current_eur_kwh"))
    if export_live is None:
        export_live = number(facts.get("pricing.export_spot_eur_kwh"))
    export_market_av = AVAILABLE if export_live is not None else UNAVAILABLE

    network = number(cfg.get("import_network_eur_kwh"))
    levies = number(cfg.get("import_levies_eur_kwh"))
    vat = number(cfg.get("import_vat_pct"))
    export_fee = number(cfg.get("export_fee_eur_kwh"))
    tariff_components = (network, levies, vat)
    tariff_component_count = sum(value is not None for value in tariff_components)
    # Market-only accounting is useful and truthful before optional retail tariff
    # components are configured. A partially configured tariff fails closed.
    import_effective = (
        round((import_market + network + levies) * (1 + vat / 100), 6)
        if import_market is not None and tariff_component_count == 3
        else import_market if import_market is not None and tariff_component_count == 0
        else None
    )
    export_effective = (
        round(export_live - export_fee, 6)
        if export_live is not None and export_fee is not None
        else export_live if export_live is not None and export_fee is None
        else None
    )
    import_effective_reason = (
        "FULL_TARIFF"
        if import_market is not None and tariff_component_count == 3
        else "MARKET_ONLY_NO_TARIFF_COMPONENTS"
        if import_market is not None and tariff_component_count == 0
        else "TARIFF_CONFIGURATION_INCOMPLETE"
    )
    export_effective_reason = (
        "FULL_TARIFF"
        if export_live is not None and export_fee is not None
        else "MARKET_ONLY_NO_EXPORT_FEE"
        if export_live is not None
        else "EXPORT_SOURCE_UNAVAILABLE"
    )

    rows = [
        # R1.89.44 current import/export prices are producer-owned market truth.
        # Optional tariff configuration augments that truth in separate effective
        # properties; it never turns a real live market price into unavailable.
        prop("pricing", "pricing.spot_eur_kwh", import_market, "EUR/kWh", availability=import_market_av, editable=import_live is None, editor="number", operation_id="energy.pricing.set_property", constraints={"min":-1,"max":5,"step":0.001}, reason_code="LIVE_SOURCE" if import_live is not None else "FALLBACK_REQUIRED"),
        prop("pricing", "pricing.spot_price_current_eur_kwh", import_market, "EUR/kWh", availability=import_market_av, editable=import_live is None, editor="number", operation_id="energy.pricing.set_property", constraints={"min":-1,"max":5,"step":0.001}, reason_code="LIVE_SOURCE" if import_live is not None else "FALLBACK_REQUIRED"),
        prop("pricing", "pricing.import_price_current_eur_kwh", import_market, "EUR/kWh", availability=import_market_av, reason_code="LIVE_SOURCE" if import_live is not None else "FALLBACK_REQUIRED"),
        prop("pricing", "pricing.export_spot_eur_kwh", export_live, "EUR/kWh", availability=export_market_av, reason_code="LIVE_SOURCE" if export_live is not None else "EXPORT_SOURCE_UNAVAILABLE"),
        prop("pricing", "pricing.export_price_current_eur_kwh", export_live, "EUR/kWh", availability=export_market_av, reason_code="LIVE_SOURCE" if export_live is not None else "EXPORT_SOURCE_UNAVAILABLE"),
        prop("pricing", "pricing.import_network_eur_kwh", network, "EUR/kWh", availability=AVAILABLE if network is not None else CONFIGURATION_REQUIRED, editable=True, editor="number", operation_id="energy.pricing.set_property", constraints={"min":0,"max":2,"step":0.001}),
        prop("pricing", "pricing.import_levies_eur_kwh", levies, "EUR/kWh", availability=AVAILABLE if levies is not None else CONFIGURATION_REQUIRED, editable=True, editor="number", operation_id="energy.pricing.set_property", constraints={"min":0,"max":2,"step":0.001}),
        prop("pricing", "pricing.import_vat_pct", vat, "%", availability=AVAILABLE if vat is not None else CONFIGURATION_REQUIRED, editable=True, editor="number", operation_id="energy.pricing.set_property", constraints={"min":0,"max":30,"step":0.1}),
        prop("pricing", "pricing.export_fee_eur_kwh", export_fee, "EUR/kWh", availability=AVAILABLE if export_fee is not None else CONFIGURATION_REQUIRED, editable=True, editor="number", operation_id="energy.pricing.set_property", constraints={"min":0,"max":2,"step":0.001}),
        prop("pricing", "pricing.import_effective_price_eur_kwh", import_effective, "EUR/kWh", availability=AVAILABLE if import_effective is not None else CONFIGURATION_REQUIRED, reason_code=import_effective_reason, quality="authoritative" if import_effective_reason == "FULL_TARIFF" else "estimated"),
        prop("pricing", "pricing.export_effective_price_eur_kwh", export_effective, "EUR/kWh", availability=AVAILABLE if export_effective is not None else CONFIGURATION_REQUIRED, reason_code=export_effective_reason, quality="authoritative" if export_effective_reason == "FULL_TARIFF" else "estimated"),
        prop("pricing", "pricing.export_compensation_current_eur_kwh", export_effective, "EUR/kWh", availability=AVAILABLE if export_effective is not None else CONFIGURATION_REQUIRED, reason_code=export_effective_reason, quality="authoritative" if export_effective_reason == "FULL_TARIFF" else "estimated"),
        prop("pricing", "pricing.future_prices", deepcopy(facts.get("pricing.future_prices")), availability=AVAILABLE if facts.get("pricing.future_prices") is not None else UNAVAILABLE),
        prop("pricing", "pricing.currency", facts.get("pricing.currency") or ("EUR" if import_market is not None or export_live is not None else None), availability=AVAILABLE if (facts.get("pricing.currency") is not None or import_market is not None or export_live is not None) else UNAVAILABLE),
        prop("pricing", "pricing.tariff", deepcopy(facts.get("pricing.tariff")), availability=AVAILABLE if facts.get("pricing.tariff") is not None else UNAVAILABLE),
        prop("pricing", "pricing.source_id", facts.get("pricing.source_id"), availability=AVAILABLE if facts.get("pricing.source_id") is not None else UNAVAILABLE),
        prop("pricing", "pricing.export_source_id", facts.get("pricing.export_source_id"), availability=AVAILABLE if facts.get("pricing.export_source_id") is not None else UNAVAILABLE),
        prop("pricing", "pricing.source_integration", facts.get("pricing.source_integration"), availability=AVAILABLE if facts.get("pricing.source_integration") is not None else UNAVAILABLE),
    ]
    return rows


def _planning_buckets(now: datetime, horizon_id: str) -> list[dict[str, Any]]:
    """Return real chronological local-day buckets, including DST transitions.

    Buckets are stepped on the UTC timeline and labelled in the Home Assistant local
    timezone. A spring-forward day therefore has 23 D1 buckets and a fall-back day 25;
    a repeated local hour is disambiguated by ``start_at``/``utc_offset``.
    """
    if now.tzinfo is None:
        now = now.astimezone()
    tz = now.tzinfo
    if horizon_id == "D1":
        start_date = now.date() + timedelta(days=1)
        end_date = start_date + timedelta(days=1)
        start_local = datetime(start_date.year, start_date.month, start_date.day, tzinfo=tz)
        end_local = datetime(end_date.year, end_date.month, end_date.day, tzinfo=tz)
    else:
        start_local = now
        end_date = now.date() + timedelta(days=1)
        end_local = datetime(end_date.year, end_date.month, end_date.day, tzinfo=tz)

    cursor = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    buckets: list[dict[str, Any]] = []
    while cursor < end_utc:
        next_boundary = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        nxt = min(next_boundary, end_utc)
        if nxt <= cursor:
            break
        local_start = cursor.astimezone(tz)
        local_end = nxt.astimezone(tz)
        duration = (nxt - cursor).total_seconds() / 3600.0
        buckets.append({
            "hour": local_start.hour,
            "duration_hours": duration,
            "runtime_minutes": max(1, int(round(duration * 60))),
            "start_at": local_start.isoformat(),
            "end_at": local_end.isoformat(),
            "utc_offset": local_start.strftime("%z"),
        })
        cursor = nxt
    return buckets

def _solar_bucket_curve(total_kwh: float | None, buckets: list[dict[str, Any]], start_hour: int, end_hour: int) -> list[float | None]:
    if total_kwh is None:
        return [None] * len(buckets)
    weighted: list[float] = []
    for bucket in buckets:
        hour = int(bucket["hour"])
        duration = float(bucket["duration_hours"])
        midpoint = hour + (1.0 - duration) + duration / 2.0 if duration < 1.0 else hour + 0.5
        if midpoint < start_hour or midpoint >= end_hour:
            weighted.append(0.0)
        else:
            x = (midpoint - start_hour) / max(1e-6, (end_hour - start_hour))
            weighted.append(max(0.0, math.sin(math.pi * x)) * duration)
    weight_sum = sum(weighted)
    if weight_sum <= 0:
        # A non-zero remaining forecast outside the configured solar window is evidence
        # we cannot time-distribute safely. Keep the aggregate, leave bucket curve zero.
        return [0.0 for _ in buckets]
    return [round(float(total_kwh) * weight / weight_sum, 6) for weight in weighted]


def _learned_baseload_fallback_kw(
    baseload_profile: dict[str, Any],
    *,
    minimum_distinct_hours: int = 12,
) -> float | None:
    """Return a broad learned fallback only after sufficient hourly evidence exists."""
    learned = []
    if isinstance(baseload_profile, dict):
        for row in baseload_profile.values():
            if not isinstance(row, dict):
                continue
            avg = number(row.get("avg_kw"))
            samples = int(row.get("samples") or 0)
            if avg is not None and samples > 0:
                learned.append(avg)
    if len(learned) < minimum_distinct_hours:
        return None
    return round(sum(learned) / len(learned), 6)


def _baseload_bucket_curve(
    buckets: list[dict[str, Any]],
    baseload_profile: dict[str, Any],
    fallback_kw: float | None,
) -> list[float | None]:
    learned_fallback = _learned_baseload_fallback_kw(baseload_profile)
    effective_fallback = fallback_kw if fallback_kw is not None else learned_fallback
    out: list[float | None] = []
    for bucket in buckets:
        hour = int(bucket["hour"])
        row = baseload_profile.get(f"{hour:02d}") if isinstance(baseload_profile, dict) else None
        avg_kw = number((row or {}).get("avg_kw")) if isinstance(row, dict) else None
        if avg_kw is None:
            avg_kw = effective_fallback
        out.append(round(avg_kw * float(bucket["duration_hours"]), 6) if avg_kw is not None else None)
    return out


def _deadline_sort_key(asset: dict[str, Any]) -> tuple[str, str]:
    raw = asset.get("deadline") or "9999-12-31T23:59:59+00:00"
    return str(raw), str(asset.get("asset_id") or "")


def _lane_totals(buckets: list[dict[str, Any]], *, complete: bool, solar: float | None, demand: float | None) -> dict[str, Any]:
    if not complete:
        return {
            "contract": "advisory_lane_totals_v1",
            "basis": "incomplete_evidence",
            "sources": {"solar_kwh": solar, "battery_out_kwh": None, "grid_in_kwh": None},
            "consumers": {"home_kwh": demand, "battery_in_kwh": None, "flexible_assets": []},
            "boundary": {"grid_out_kwh": None},
            "source_total_kwh": None,
            "use_total_kwh": None,
            "balance_delta_kwh": None,
        }
    def participant_energy(bucket: dict[str, Any], lane: str, participant_id: str) -> float:
        for row in bucket.get(lane) or []:
            if str((row or {}).get("participant_id") or "") != participant_id:
                continue
            value = number((row or {}).get("planned_supply_kwh"))
            if value is None:
                value = number((row or {}).get("planned_demand_kwh"))
            return value or 0.0
        return 0.0

    solar_sum = round(sum(participant_energy(b, "advisory_source_lane", "solar") for b in buckets), 3)
    batt_sum = round(sum(participant_energy(b, "advisory_source_lane", "battery") for b in buckets), 3)
    grid_sum = round(sum(participant_energy(b, "advisory_source_lane", "grid") for b in buckets), 3)
    home_sum = round(sum(participant_energy(b, "advisory_consumer_lane", "home") for b in buckets), 3)
    flex_by_asset: dict[str, float] = {}
    for bucket in buckets:
        for row in bucket.get("advisory_consumer_lane") or []:
            aid = str((row or {}).get("participant_id") or "")
            if not aid or aid == "home":
                continue
            energy = number((row or {}).get("planned_demand_kwh"))
            if energy is None:
                continue
            flex_by_asset[aid] = round(flex_by_asset.get(aid, 0.0) + energy, 3)
    flex_sum = round(sum(flex_by_asset.values()), 3)
    export_sum = round(sum(number((b.get("advisory_boundary_flows") or {}).get("grid_export_kwh")) or 0.0 for b in buckets), 3)
    source_total = round(solar_sum + batt_sum + grid_sum, 3)
    use_total = round(home_sum + flex_sum + export_sum, 3)
    return {
        "contract": "advisory_lane_totals_v1",
        "basis": "sum_of_published_advisory_bucket_lanes",
        "sources": {"solar_kwh": solar_sum, "battery_out_kwh": batt_sum, "grid_in_kwh": grid_sum},
        "consumers": {
            "home_kwh": home_sum,
            "battery_in_kwh": 0.0,
            "flexible_assets": [{"asset_id": key, "planned_energy_kwh": value} for key, value in sorted(flex_by_asset.items())],
        },
        "boundary": {"grid_out_kwh": export_sum},
        "source_total_kwh": source_total,
        "use_total_kwh": use_total,
        "balance_delta_kwh": round(source_total - use_total, 6),
    }


def deterministic_plan(facts: dict[str, Any], settings: dict[str, Any], flexible_assets: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    """Deterministic D0/D1 advisory plan with chronological evidence semantics.

    D0 means *now until local midnight*; D1 is the full following day.  Battery
    support is carried chronologically from D0 into D1, minimum runtime is respected
    when the producer publishes it, and allocations are deterministic by deadline then
    asset id.  This remains advisory: physical command execution has its own live gates.
    """
    now = now or datetime.now().astimezone()
    strategy = settings.get("strategy") or {}
    planning_cfg = settings.get("planning") or {}
    baseload_profile = settings.get("baseload_profile") or {}
    mode = strategy.get("energy.automation_mode") or strategy.get("energy.operating_mode") or "advice"
    solar_today = number(facts.get("forecast.solar_remaining_today_kwh"))
    solar_tomorrow = number(facts.get("forecast.solar_tomorrow_kwh"))

    capacity = number(facts.get("battery.capacity_kwh"))
    battery_available = number(facts.get("battery.available_kwh"))
    reserve_pct = number(strategy.get("battery.reserve_target_pct")) or 20.0
    if strategy.get("resilience.objective") == "resilience_first":
        reserve_pct = max(reserve_pct, 30.0)
    protected = capacity * reserve_pct / 100.0 if capacity is not None else None
    usable_battery = max(0.0, battery_available - (protected or 0.0)) if battery_available is not None else None
    battery_policy = strategy.get("flexible_loads.battery_policy", "minimum_power_bridge")
    if battery_policy in {"never", "avoid"} and usable_battery is not None:
        usable_battery = 0.0

    active_assets = sorted(
        [asset for asset in flexible_assets if not (settings.get("holds") or {}).get(asset.get("asset_id"))],
        key=_deadline_sort_key,
    )
    original_need = {str(asset.get("asset_id")): max(0.0, number(asset.get("energy_to_target_kwh")) or 0.0) for asset in active_assets}

    price_by = by_key(pricing_properties(facts, settings))
    import_price = number((price_by.get("pricing.import_price_current_eur_kwh") or {}).get("value"))
    raw_intervals = facts.get("pricing.future_prices")
    future_intervals: list[dict[str, Any]] = []
    for value in raw_intervals if isinstance(raw_intervals, list) else []:
        future_intervals.extend(value if isinstance(value, list) else [value])
    future_intervals = [row for row in future_intervals if isinstance(row, dict)]
    grid_policy = strategy.get("flexible_loads.grid_policy", "cheap_only")
    objective = strategy.get("flexible_loads.objective", "balanced")
    solar_policy = strategy.get("flexible_loads.solar_policy", "prefer")

    def price_for_bucket(meta: dict[str, Any]) -> float | None:
        try:
            start = datetime.fromisoformat(str(meta.get("start_at") or meta.get("start_time")).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(meta.get("end_at") or meta.get("end_time")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return import_price
        for row in future_intervals:
            try:
                at = datetime.fromisoformat(str(row.get("time") or row.get("start") or row.get("start_time")).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if at.tzinfo is None and start.tzinfo is not None:
                at = at.replace(tzinfo=start.tzinfo)
            if start <= at < end:
                price = number(row.get("price") if "price" in row else row.get("value"))
                if price is not None:
                    return price
        return import_price

    def grid_allowed(price: float | None) -> bool:
        if solar_policy == "only" or grid_policy in {"never", "not_applicable", "avoid_or_unavailable"}:
            return False
        if grid_policy == "always_allowed":
            return True
        if grid_policy == "cheap_only":
            return price is not None and price <= 0.30
        if grid_policy == "if_needed_for_minimum":
            return objective in {"deadline_first", "resilience_first"}
        return grid_policy == "if_needed_for_preferred"
    fallback_kw = number(planning_cfg.get("explicit_baseload_fallback_kw"))
    bootstrap_kw = number(planning_cfg.get("bootstrap_baseload_kw"))
    if fallback_kw is None:
        fallback_kw = bootstrap_kw
    window_start = int(planning_cfg.get("solar_window_start_hour", 7))
    window_end = int(planning_cfg.get("solar_window_end_hour", 20))

    def build_horizon(
        horizon_id: str,
        solar_total: float | None,
        asset_remaining: dict[str, float],
        battery_start: float | None,
    ) -> tuple[dict[str, Any], dict[str, float], float | None]:
        bucket_meta = _planning_buckets(now, horizon_id)
        solar_curve = _solar_bucket_curve(solar_total, bucket_meta, window_start, window_end)
        home_curve = _baseload_bucket_curve(bucket_meta, baseload_profile, fallback_kw)
        demand = round(sum(v for v in home_curve if v is not None), 4) if home_curve and all(v is not None for v in home_curve) else None
        requested = round(sum(asset_remaining.values()), 4)
        complete = solar_total is not None and demand is not None
        warnings: list[str] = [] if complete else ["incomplete_forecast_or_demand_evidence"]
        if bootstrap_kw is not None and number(planning_cfg.get("explicit_baseload_fallback_kw")) is None:
            warnings.append("baseload_bootstrap_from_metered_home_average")
        learned_fallback = _learned_baseload_fallback_kw(baseload_profile)
        if fallback_kw is None and learned_fallback is not None:
            missing_hours = [
                int(bucket["hour"])
                for bucket in bucket_meta
                if number(((baseload_profile.get(f"{int(bucket['hour']):02d}") or {}) if isinstance(baseload_profile, dict) else {}).get("avg_kw")) is None
            ]
            if missing_hours:
                warnings.append("missing_hour_baseload_filled_from_learned_profile_mean")
        battery_remaining = battery_start
        runtime_remaining: dict[str, int] = {aid: 0 for aid in asset_remaining}
        served_count: dict[str, int] = {aid: 0 for aid in asset_remaining}
        buckets: list[dict[str, Any]] = []

        def can_sustain_minimum(start_index: int, min_power: float, minimum_runtime: int, battery_at_start: float | None) -> bool:
            if minimum_runtime <= 0 or min_power <= 0:
                return True
            remaining_minutes = minimum_runtime
            battery_sim = max(0.0, battery_at_start or 0.0) if battery_at_start is not None else 0.0
            for future_index in range(start_index, len(bucket_meta)):
                if remaining_minutes <= 0:
                    return True
                future_solar = solar_curve[future_index]
                future_home = home_curve[future_index]
                if future_solar is None or future_home is None:
                    return False
                available_minutes = min(int(bucket_meta[future_index]["runtime_minutes"]), remaining_minutes)
                fraction = available_minutes / 60.0
                # Home demand has first claim on local supply. Battery may bridge its deficit.
                solar_for_segment = float(future_solar) * (available_minutes / max(1, int(bucket_meta[future_index]["runtime_minutes"])))
                home_for_segment = float(future_home) * (available_minutes / max(1, int(bucket_meta[future_index]["runtime_minutes"])))
                home_deficit = max(0.0, home_for_segment - solar_for_segment)
                battery_for_home = min(battery_sim, home_deficit)
                battery_sim -= battery_for_home
                bucket_grid_allowed = grid_allowed(price_for_bucket(bucket_meta[future_index]))
                if home_deficit - battery_for_home > 1e-6 and not bucket_grid_allowed:
                    return False
                surplus = max(0.0, solar_for_segment - home_for_segment)
                needed = min_power * fraction
                local = surplus + battery_sim
                if local + 1e-6 < needed and not bucket_grid_allowed:
                    return False
                if not bucket_grid_allowed:
                    battery_sim -= max(0.0, needed - surplus)
                remaining_minutes -= available_minutes
            return remaining_minutes <= 0

        for index, meta in enumerate(bucket_meta):
            duration = float(meta["duration_hours"])
            max_minutes = int(meta["runtime_minutes"])
            solar_b = solar_curve[index]
            home_b = home_curve[index]
            bucket_price = price_for_bucket(meta)
            bucket_grid_allowed = grid_allowed(bucket_price)
            local_surplus = max(0.0, (solar_b or 0.0) - (home_b or 0.0)) if solar_b is not None and home_b is not None else 0.0
            local_energy_for_flex = local_surplus + max(0.0, battery_remaining or 0.0)
            available_for_flex = float("inf") if bucket_grid_allowed else local_energy_for_flex
            flex_allocs: list[dict[str, Any]] = []
            flex_energy = 0.0

            if complete:
                # Continue previously started minimum-runtime windows first, then use
                # deterministic deadline/asset ordering for newly starting loads.
                ordered = sorted(
                    active_assets,
                    key=lambda a: (
                        0 if runtime_remaining.get(str(a.get("asset_id"))) else 1,
                        _deadline_sort_key(a)[0],
                        served_count.get(str(a.get("asset_id")), 0),
                        _deadline_sort_key(a)[1],
                    ),
                )
                for asset in ordered:
                    aid = str(asset.get("asset_id") or "")
                    need = asset_remaining.get(aid, 0.0)
                    if not aid or need <= 1e-9 or available_for_flex <= 1e-9:
                        continue
                    min_power = max(0.0, number(asset.get("min_power_kw")) or 0.0)
                    max_power = max(min_power, number(asset.get("max_power_kw")) or min_power or need / max(duration, 1e-6))
                    minimum_runtime = max(0, int(round(number(asset.get("minimum_runtime_minutes")) or 0)))
                    continuing = runtime_remaining.get(aid, 0) > 0
                    required_minutes = min(max_minutes, runtime_remaining.get(aid, 0)) if continuing else min(max_minutes, minimum_runtime)
                    total_minimum_energy = min_power * (minimum_runtime / 60.0) if minimum_runtime > 0 else 0.0
                    if not continuing and total_minimum_energy > need + 1e-6:
                        warnings.append(f"minimum_runtime_exceeds_remaining_need:{aid}")
                        continue
                    if not continuing and not can_sustain_minimum(index, min_power, minimum_runtime, battery_remaining):
                        continue
                    min_energy = min_power * (required_minutes / 60.0) if required_minutes > 0 else 0.0
                    if not bucket_grid_allowed and min_energy > available_for_flex + 1e-6:
                        continue
                    max_energy = max_power * duration
                    energy = min(need, max_energy, available_for_flex)
                    if energy <= 1e-9:
                        continue
                    if min_power > 0:
                        runtime_minutes = min(max_minutes, max(required_minutes, int(math.ceil((energy / min_power) * 60))))
                        runtime_minutes = max(1, runtime_minutes)
                        planned_power = min(max_power, energy / max(runtime_minutes / 60.0, 1e-6))
                        if planned_power + 1e-9 < min_power:
                            planned_power = min_power
                            energy = min(need, available_for_flex, planned_power * runtime_minutes / 60.0)
                    else:
                        runtime_minutes = max_minutes if energy > 0 else 0
                        planned_power = energy / max(duration, 1e-6) if energy > 0 else 0.0
                    if energy <= 1e-9 or runtime_minutes <= 0:
                        continue
                    remaining_runtime = max(0, (runtime_remaining.get(aid, 0) if continuing else minimum_runtime) - runtime_minutes)
                    runtime_remaining[aid] = remaining_runtime
                    served_count[aid] = served_count.get(aid, 0) + 1
                    asset_remaining[aid] = max(0.0, need - energy)
                    available_for_flex -= energy
                    flex_energy += energy
                    flex_allocs.append({
                        "asset_id": aid,
                        "planned_power_kw": round(planned_power, 3),
                        "planned_energy_kwh": round(energy, 4),
                        "runtime_minutes": runtime_minutes,
                        "minimum_runtime_minutes": minimum_runtime,
                        "minimum_power_kw": round(min_power, 3),
                        "effective_min_power_kw": round(min_power, 3),
                        "effective_max_power_kw": round(max_power, 3),
                        "allocation_state": "scheduled" if mode == "automatic" else "advisory",
                        "plan_execution_allowed": mode == "automatic",
                        "planned_import_price_eur_kwh": bucket_price,
                    })

            source_need = home_b + flex_energy if home_b is not None else None
            battery_start_bucket = battery_remaining
            battery_out = grid_in = grid_out = None
            if solar_b is not None and source_need is not None:
                deficit = max(0.0, source_need - solar_b)
                battery_out = min(max(0.0, battery_remaining or 0.0), deficit) if battery_remaining is not None else 0.0
                if battery_remaining is not None:
                    battery_remaining = max(0.0, battery_remaining - battery_out)
                grid_in = max(0.0, deficit - (battery_out or 0.0))
                grid_out = max(0.0, solar_b - source_need)
            source_total = (solar_b or 0.0) + (battery_out or 0.0) + (grid_in or 0.0) if solar_b is not None and source_need is not None else None
            use_total = source_need + (grid_out or 0.0) if source_need is not None and grid_out is not None else None
            source_lane = [
                {
                    "participant_id": "solar",
                    "display_name": "Solar",
                    "participant_type": "producer",
                    "lane_role": "source",
                    "flow_direction": "production",
                    "planned_supply_kwh": solar_b,
                    "planning_state": "forecast" if solar_b is not None else "unavailable",
                },
                {
                    "participant_id": "battery",
                    "display_name": "Home Battery",
                    "participant_type": "storage",
                    "lane_role": "source",
                    "flow_direction": "discharge" if (battery_out or 0.0) > 0 else "idle",
                    "planned_supply_kwh": round(battery_out, 4) if battery_out is not None else None,
                    "planning_state": "planned" if battery_out is not None else "unavailable",
                },
                {
                    "participant_id": "grid",
                    "display_name": "Grid",
                    "participant_type": "grid_connection",
                    "lane_role": "source",
                    "flow_direction": "import" if (grid_in or 0.0) > 0 else "idle",
                    "planned_supply_kwh": round(grid_in, 4) if grid_in is not None else None,
                    "planning_state": "residual_supply" if (grid_in or 0.0) > 0 else "not_required",
                },
            ]
            consumer_lane = [
                {
                    "participant_id": "home",
                    "display_name": "Home Consumption",
                    "participant_type": "fixed_consumer",
                    "lane_role": "consumer",
                    "flow_direction": "consume",
                    "planned_demand_kwh": home_b,
                    "planning_state": "forecast" if home_b is not None else "unavailable",
                },
                *[
                    {
                        **deepcopy(allocation),
                        "participant_id": allocation.get("asset_id"),
                        "lane_role": "consumer",
                        "flow_direction": "charge",
                        "planned_demand_kwh": allocation.get("planned_energy_kwh"),
                        "planning_state": "planned",
                    }
                    for allocation in flex_allocs
                ],
            ]
            buckets.append({
                "bucket_id": f"{horizon_id}:{int(meta['hour']):02d}",
                "hour": int(meta["hour"]),
                "start_time": meta.get("start_at"),
                "end_time": meta.get("end_at"),
                "duration_minutes": max_minutes,
                "duration_hours": round(duration, 6),
                "runtime_minutes": max_minutes,
                "estimated": True,
                "solar_forecast_kwh": solar_b,
                "base_demand_forecast_kwh": home_b,
                "planned_flexible_kwh": round(flex_energy, 4),
                "expected_grid_import_kwh": round(grid_in, 4) if grid_in is not None else None,
                "expected_grid_export_kwh": round(grid_out, 4) if grid_out is not None else None,
                "advisory_source_lane": source_lane,
                "advisory_consumer_lane": consumer_lane,
                "advisory_boundary_flows": {
                    "grid_import_kwh": round(grid_in, 4) if grid_in is not None else None,
                    "grid_export_kwh": round(grid_out, 4) if grid_out is not None else None,
                },
                "advisory_lane_balance_delta_kwh": round(source_total - use_total, 6) if source_total is not None and use_total is not None else None,
                "planning_state": "ready" if complete else "incomplete",
                "forecast_quality": "estimated" if complete else "incomplete",
                "import_price_eur_kwh": bucket_price,
                "grid_policy_allows_import": bucket_grid_allowed,
                "estimation_disclosure": "Forecast and learned baseload; advisory only.",
                "battery_ledger": {
                    "start_usable_kwh": round(battery_start_bucket, 4) if battery_start_bucket is not None else None,
                    "discharge_kwh": round(battery_out, 4) if battery_out is not None else None,
                    "end_usable_kwh": round(battery_remaining, 4) if battery_remaining is not None else None,
                    "protected_reserve_kwh": round(protected, 4) if protected is not None else None,
                },
                "asset_allocations": flex_allocs,
            })

        scheduled = round(requested - sum(asset_remaining.values()), 4)
        deferred = round(sum(asset_remaining.values()), 4)
        if deferred > 0:
            warnings.append("flexible_need_deferred_by_strategy_or_capacity")
        lane_totals = _lane_totals(buckets, complete=complete, solar=solar_total, demand=demand)
        grid_import = number((lane_totals.get("sources") or {}).get("grid_in_kwh"))
        grid_export = number((lane_totals.get("boundary") or {}).get("grid_out_kwh"))
        battery_support = number((lane_totals.get("sources") or {}).get("battery_out_kwh"))
        return ({
            "horizon_id": horizon_id,
            "label": "Today" if horizon_id == "D0" else "Tomorrow",
            "mode": mode,
            "time_scope": "remaining_today" if horizon_id == "D0" else "full_day_tomorrow",
            "supply": {
                "solar_kwh": solar_total,
                "solar_forecast_kwh": solar_total,
                "solar_remaining_kwh": solar_total if horizon_id == "D0" else None,
                "battery_support_kwh": battery_support,
                "grid_import_kwh": grid_import,
                "total_usable_supply_kwh": round((solar_total or 0.0) + (battery_support or 0.0) + (grid_import or 0.0), 4) if complete else None,
            },
            "demand": {
                "home_kwh": demand,
                "home_consumption_kwh": demand,
                "home_consumption_forecast_kwh": demand,
                "flexible_known_need_kwh": requested,
                "flexible_scheduled_kwh": scheduled,
                "flexible_loads_kwh": scheduled,
                "flexible_deferred_kwh": deferred,
                "total_kwh": round(demand + scheduled, 4) if demand is not None else None,
                "total_expected_demand_kwh": round(demand + scheduled, 4) if demand is not None else None,
                "expected_demand_kwh": round(demand + scheduled, 4) if demand is not None else None,
            },
            "balance": {
                "expected_grid_import_kwh": grid_import,
                "expected_grid_export_kwh": grid_export,
                "grid_balance_kwh": round(grid_import - grid_export, 4) if grid_import is not None and grid_export is not None else None,
                "balance_kwh": round(grid_import - grid_export, 4) if grid_import is not None and grid_export is not None else None,
                "outlook_balance_kwh": round(grid_import - grid_export, 4) if grid_import is not None and grid_export is not None else None,
            },
            "candidates": [aid for aid, value in sorted(asset_remaining.items()) if original_need.get(aid, 0.0) > 0],
            "quality": {"availability": AVAILABLE if complete else INCOMPLETE, "estimated": True, "warnings": sorted(set(warnings))},
            "policy_evidence": {"grid_policy": grid_policy, "grid_allowed_for_flexible": any(grid_allowed(price_for_bucket(meta)) for meta in bucket_meta), "grid_allowed_bucket_count": sum(1 for meta in bucket_meta if grid_allowed(price_for_bucket(meta))), "grid_bucket_count": len(bucket_meta), "solar_policy": solar_policy, "battery_policy": battery_policy, "objective": objective, "current_import_price_eur_kwh": import_price, "reserve_target_pct": reserve_pct},
            "battery_ledger": {"start_usable_kwh": round(battery_start, 4) if battery_start is not None else None, "end_usable_kwh": round(battery_remaining, 4) if battery_remaining is not None else None, "protected_reserve_kwh": round(protected, 4) if protected is not None else None},
            "source_refs": ["sensor.energy_forecast_property_index", "sensor.energy_consumption_property_index", "sensor.energy_flexible_asset_index", "sensor.energy_strategy_effective_index", "sensor.energy_pricing_property_index"],
            "summary": {"lane_totals": lane_totals},
            "buckets": buckets,
        }, asset_remaining, battery_remaining)

    remaining = dict(original_need)
    d0, remaining, battery_after_d0 = build_horizon("D0", solar_today, remaining, usable_battery)
    d1, remaining, battery_after_d1 = build_horizon("D1", solar_tomorrow, remaining, battery_after_d0)
    unresolved = round(sum(remaining.values()), 4)
    baseline_plan = {
        "contract": "energy_baseline_plan_v1",
        "horizons": {
            horizon["horizon_id"]: {
                "supply": deepcopy(horizon.get("supply") or {}),
                "home_demand_kwh": (horizon.get("demand") or {}).get("home_kwh"),
                "balance": deepcopy(horizon.get("balance") or {}),
                "quality": deepcopy(horizon.get("quality") or {}),
            }
            for horizon in (d0, d1)
        },
    }
    flexible_plan = {
        "contract": "energy_flexible_plan_v1",
        "participating_asset_count": len(active_assets),
        "participating_asset_ids": [str(asset.get("asset_id")) for asset in active_assets if asset.get("asset_id")],
        "known_need_kwh": round(sum(original_need.values()), 4),
        "unresolved_need_kwh": unresolved,
        "horizons": {
            horizon["horizon_id"]: {
                "scheduled_kwh": (horizon.get("demand") or {}).get("flexible_scheduled_kwh"),
                "deferred_kwh": (horizon.get("demand") or {}).get("flexible_deferred_kwh"),
                "candidates": deepcopy(horizon.get("candidates") or []),
                "quality": deepcopy(horizon.get("quality") or {}),
            }
            for horizon in (d0, d1)
        },
    }
    return {
        "plan_id": f"deterministic:{now.strftime('%Y%m%d%H%M')}",
        "generated_at": now.isoformat(),
        "planning_horizons": {"D0": d0, "D1": d1},
        "planning_horizons_json": [d0, d1],
        "baseline_plan": baseline_plan,
        "flexible_plan": flexible_plan,
        "unresolved_flexible_need_kwh": unresolved,
        "battery_ledger": {"initial_usable_kwh": usable_battery, "after_d0_kwh": battery_after_d0, "after_d1_kwh": battery_after_d1},
        "health": "OK" if d0["quality"]["availability"] == AVAILABLE else "DEGRADED",
        "reason": "deterministic_chronological_capacity_price_policy_aware_plan",
    }

def automatic_execution_decision(grid_export_kw: Any, asset: dict[str, Any], planning_hold: bool = False) -> dict[str, Any]:
    """Fail-closed automatic execution gate based on trusted current export.

    Battery charging or forecasted surplus is never counted as allocatable export.
    """
    export = number(grid_export_kw)
    need = number(asset.get("energy_to_target_kwh")) or 0.0
    min_power = number(asset.get("min_power_kw")) or 0.0
    max_power = number(asset.get("max_power_kw")) or min_power
    running = str(asset.get("operating_state") or "").lower() in {"running", "charging", "active", "on"}
    if planning_hold:
        return {"action": "hold", "reason": "planning_hold", "target_power_kw": None}
    if export is None:
        return {"action": "none", "reason": "trusted_grid_export_unavailable", "target_power_kw": None}
    if need > 0.05 and min_power > 0 and export + 1e-6 >= min_power:
        return {"action": "start", "reason": "trusted_current_grid_export_meets_minimum_power", "target_power_kw": round(min(max_power, max(min_power, export)), 3)}
    if running and export < 0.05:
        return {"action": "stop", "reason": "trusted_current_grid_export_no_longer_available", "target_power_kw": None}
    return {"action": "none", "reason": "automatic_gate_not_met", "target_power_kw": None}


def protective_execution_decision(grid_import_kw: Any, battery_power_kw: Any, asset: dict[str, Any]) -> dict[str, Any]:
    """Independent negative safety guard; it may only reduce/stop load."""
    running = str(asset.get("operating_state") or "").lower() in {"running","charging","active","on"}
    if not running:
        return {"action":"none","reason":"asset_not_running","target_power_kw":None}
    grid_import = number(grid_import_kw)
    battery_discharge = number(battery_power_kw)
    if grid_import is not None and grid_import > 0.30:
        return {"action":"stop","reason":"protective_grid_import_detected","target_power_kw":None}
    if battery_discharge is not None and battery_discharge > 0.30:
        return {"action":"stop","reason":"protective_battery_discharge_detected","target_power_kw":None}
    return {"action":"none","reason":"protective_gate_clear","target_power_kw":None}


def intelligence(plan: dict[str, Any], facts: dict[str, Any], settings: dict[str, Any], flexible_assets: list[dict[str, Any]]) -> dict[str, Any]:
    mode=(settings.get("strategy") or {}).get("energy.automation_mode") or (settings.get("strategy") or {}).get("energy.operating_mode","advice")
    d0=(plan.get("planning_horizons") or {}).get("D0") or {}
    balance=d0.get("balance") or {}
    gi=number(balance.get("expected_grid_import_kwh"))
    ge=number(balance.get("expected_grid_export_kwh"))
    needs=[a for a in flexible_assets if (number(a.get("energy_to_target_kwh")) or 0)>0]
    plan_availability = ((d0.get("quality") or {}).get("availability"))
    if mode == "disabled":
        decision="HOLD"; rec="Energy automation is disabled."; reason="strategy_disabled"; readiness=UNAVAILABLE
    elif plan_availability != AVAILABLE:
        decision="NOT_EVALUATED"; rec=None; reason="planning_inputs_incomplete"; readiness=UNAVAILABLE
    elif needs and ge is not None and ge > 0.5:
        decision="USE_SURPLUS"; rec=f"Use expected surplus for {needs[0].get('display_name') or needs[0].get('asset_id')}."; reason="forecast_surplus_and_flexible_need"; readiness=AVAILABLE
    elif needs and gi is not None and gi > 0:
        decision="SCHEDULE"; rec=f"Schedule {needs[0].get('display_name') or needs[0].get('asset_id')} against available solar and price windows."; reason="flexible_need_requires_planning"; readiness=AVAILABLE
    else:
        decision="HOLD"; rec="No immediate Energy action is required."; reason="balanced_or_no_flexible_need"; readiness=AVAILABLE
    trust = "Medium" if plan.get("health") != "OK" else "High"
    return {
        "decision": decision,
        "recommendation": rec,
        "reason": reason,
        "availability": readiness,
        "trust": trust,
        "confidence": trust,
        "product_state": "READY" if readiness == AVAILABLE else "NOT_AVAILABLE",
        "status": "READY" if readiness == AVAILABLE else "NOT_AVAILABLE",
        "automation_mode": mode,
        "selected_flexible_load_id": needs[0].get("asset_id") if needs else None,
    }
