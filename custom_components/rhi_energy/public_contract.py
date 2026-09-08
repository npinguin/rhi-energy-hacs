"""R1.84.2-compatible public Energy contract projected from the V2 runtime.

The legacy UX consumes these entities and attributes directly.  The projection
keeps that public shape while every value comes from the V2 canonical runtime,
persistent Energy configuration, metering, or producer-owned command contracts.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

from .compat_core import (
    AVAILABLE,
    CONFIGURATION_REQUIRED,
    INCOMPLETE,
    UNAVAILABLE,
    UNSUPPORTED,
    by_key,
    jdump,
    metering_rows,
    number,
    overview_snapshot,
    pricing_properties,
    prop,
    split_battery_power,
    strategy_properties,
)
from .const import LEGACY_CONTRACT_VERSION, LEGACY_PUBLIC_ENTITIES, RELEASE


def _status_for_rows(rows: list[dict[str, Any]], *, empty: str = UNAVAILABLE) -> str:
    if not rows:
        return empty
    values = [str(r.get("availability") or UNAVAILABLE) for r in rows]
    if any(v == AVAILABLE for v in values):
        return AVAILABLE
    if any(v == CONFIGURATION_REQUIRED for v in values):
        return CONFIGURATION_REQUIRED
    if any(v == INCOMPLETE for v in values):
        return INCOMPLETE
    if all(v == UNSUPPORTED for v in values):
        return UNSUPPORTED
    return UNAVAILABLE


def _base(schema: str) -> dict[str, Any]:
    return {
        "contract_visibility": "ux_safe",
        "contract_version": LEGACY_CONTRACT_VERSION,
        "release": RELEASE,
        "schema_version": 1,
        "index_schema": schema,
        "runtime_owner": "rhi_energy",
        "legacy_yaml_runtime_required": False,
    }


def _property_attrs(rows: list[dict[str, Any]], schema: str, **extra: Any) -> dict[str, Any]:
    health = _status_for_rows(rows)
    attrs = _base(schema)
    attrs.update(
        {
            "properties": jdump(rows),
            "properties_json": jdump(rows),
            "properties_by_key": jdump(by_key(rows)),
            "health": "OK" if health == AVAILABLE else health,
            "health_reason": "canonical_v2_runtime_projection" if health == AVAILABLE else "required_domain_evidence_not_fully_available",
            "product_status": health,
            "product_reason": "Canonical V2 runtime evidence is available." if health == AVAILABLE else "Required domain evidence is not fully available.",
            **extra,
        }
    )
    return attrs


def _fact_rows(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    f = snapshot.get("facts") or {}
    settings = snapshot.get("settings") or {}
    charge, discharge = split_battery_power(number(f.get("battery.power_kw")))
    solar = [
        prop("solar", "solar.power_kw", number(f.get("solar.power_kw")), "kW"),
        prop("solar", "solar.energy_today_kwh", number(f.get("solar.energy_today_kwh")), "kWh"),
        prop("solar", "solar.health", f.get("solar.health"), availability=AVAILABLE if f.get("solar.health") else UNAVAILABLE),
    ]
    # Surplus is a domain fact derived from the same canonical Energy balance,
    # not recomputed by the UX.
    solar_kw = number(f.get("solar.power_kw")); home_kw = number(f.get("home_consumption.power_kw"))
    surplus = max(0.0, solar_kw - home_kw) if solar_kw is not None and home_kw is not None else None
    solar.append(prop("solar", "solar.usable_surplus_kw", round(surplus, 4) if surplus is not None else None, "kW"))

    reserve_actual = number(f.get("battery.reserve_soc_pct"))
    battery = [
        prop("battery", "battery.power_kw", number(f.get("battery.power_kw")), "kW"),
        prop("battery", "battery.charge_power_kw", charge, "kW"),
        prop("battery", "battery.discharge_power_kw", discharge, "kW"),
        prop("battery", "battery.soc_pct", number(f.get("battery.soc_pct")), "%"),
        prop("battery", "battery.capacity_kwh", number(f.get("battery.capacity_kwh")), "kWh"),
        prop("battery", "battery.available_kwh", number(f.get("battery.available_kwh")), "kWh"),
        prop("battery", "battery.health", f.get("battery.health"), availability=AVAILABLE if f.get("battery.health") else UNAVAILABLE),
    ]
    if reserve_actual is not None or snapshot.get("battery_reserve_write_supported"):
        battery.append(
            prop(
                "battery",
                "battery.reserve_soc_pct",
                reserve_actual,
                "%",
                editable=bool(snapshot.get("battery_reserve_write_supported")),
                editor="slider",
                constraints={"min": 0, "max": 100, "step": 1},
                operation_id="energy.property.write",
                availability=AVAILABLE if reserve_actual is not None else UNAVAILABLE,
            )
        )
    for unit in snapshot.get("battery_units") or []:
        aid = str(unit.get("asset_id") or "battery_unit")
        for key, unit_name in (("power_kw", "kW"), ("soc_pct", "%"), ("capacity_kwh", "kWh"), ("available_kwh", "kWh")):
            battery.append(prop(aid, f"{aid}.{key}", number(unit.get(key)), unit_name))

    grid = [
        prop("grid", "grid.net_power_kw", number(f.get("grid.net_power_kw")), "kW"),
        prop("grid", "grid_import.power_kw", number(f.get("grid_import.power_kw")), "kW"),
        prop("grid", "grid_export.power_kw", number(f.get("grid_export.power_kw")), "kW"),
        prop("grid", "grid_import.energy_total_kwh", number(f.get("metering.grid_import_total_kwh")), "kWh"),
        prop("grid", "grid_export.energy_total_kwh", number(f.get("metering.grid_export_total_kwh")), "kWh"),
    ]
    consumption = [
        prop("consumption", "home_consumption.power_kw", number(f.get("home_consumption.power_kw")), "kW"),
        prop("consumption", "consumption.power_kw", number(f.get("consumption.power_kw")), "kW"),
        prop("consumption", "consumption.health", f.get("consumption.health"), availability=AVAILABLE if f.get("consumption.health") else UNAVAILABLE),
    ]
    forecast = [
        prop("forecast", "forecast.solar_power_kw", number(f.get("forecast.solar_power_kw")), "kW"),
        prop("forecast", "forecast.solar_today_kwh", number(f.get("forecast.solar_today_kwh")), "kWh"),
        prop("forecast", "forecast.solar_remaining_today_kwh", number(f.get("forecast.solar_remaining_today_kwh")), "kWh"),
        prop("forecast", "forecast.solar_tomorrow_kwh", number(f.get("forecast.solar_tomorrow_kwh")), "kWh"),
        prop("forecast", "forecast.peak_time", f.get("forecast.peak_time"), availability=AVAILABLE if f.get("forecast.peak_time") is not None else UNAVAILABLE),
    ]
    return {
        "solar": solar,
        "battery": battery,
        "grid": grid,
        "consumption": consumption,
        "forecast": forecast,
        "pricing": pricing_properties(f, settings),
        "strategy": strategy_properties(settings),
    }


def _metering_projection(store_data: dict[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    settings = store_data.get("settings") or {}
    selected = str(settings.get("metering_selected_period") or "today")
    metering = store_data.get("metering") or {}
    rows = metering_rows(metering)
    by_id = {r["period_id"]: r for r in rows}
    current = deepcopy(by_id.get(selected) or {})
    status = current.get("availability") or UNAVAILABLE
    period_choices=[{"value": x, "label": {"today":"Today","week":"This week","month":"This month","year":"This year"}[x]} for x in ("today","week","month","year")]
    props = [
        prop("metering","metering.selected_period",selected,editable=True,editor="select",constraints={"allowed":["today","week","month","year"]},choices=period_choices,operation_id="energy.metering.set_period"),
        prop("metering","metering.selected_period_id",selected,editable=True,editor="select",constraints={"allowed":["today","week","month","year"]},choices=period_choices,operation_id="energy.metering.set_period"),
    ]
    for key in ("solar_kwh", "grid_import_kwh", "grid_export_kwh", "consumption_kwh", "battery_charge_kwh", "battery_discharge_kwh", "flexible_load_kwh"):
        props.append(prop("metering", f"metering.{selected}.{key}", current.get(key), "kWh", availability=status))
    return status, {"selected_period_id": selected, "periods": rows, "periods_by_id": by_id, "selected": current}, props


def _flexible_projection(snapshot: dict[str, Any], command_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    command_by_target: dict[str, list[dict[str, Any]]] = {}
    for row in command_rows:
        command_by_target.setdefault(str(row.get("target_asset_id") or ""), []).append(row)
    assets = []
    props = []
    holds = ((snapshot.get("settings") or {}).get("holds") or {})
    for raw in snapshot.get("flexible_assets") or []:
        asset = deepcopy(raw)
        aid = str(asset.get("asset_id"))
        rows = command_by_target.get(aid, [])
        adjust = next((x for x in rows if x.get("command_id") == "energy.command.set_flexible_load_power"), None)
        asset.update(
            {
                "energy_asset_class": asset.get("energy_asset_class") or ("vehicle" if str(asset.get("source_domain") or "").lower() == "mobility" else "generic_flexible_load"),
                "planning_hold": bool(holds.get(aid)),
                "command_readiness": AVAILABLE if any(r.get("availability") == AVAILABLE for r in rows) else UNAVAILABLE,
                "command_refs": {str(r.get("role")): r.get("command_instance_id") for r in rows},
            }
        )
        assets.append(asset)
        props.extend(
            [
                prop(aid, f"{aid}.power_kw", number(asset.get("power_kw")), "kW"),
                prop(aid, f"{aid}.energy_to_target_kwh", number(asset.get("energy_to_target_kwh")), "kWh"),
                prop(
                    aid,
                    f"{aid}.requested_power_kw",
                    number(asset.get("requested_power_kw")),
                    "kW",
                    editable=bool(adjust and adjust.get("availability") == AVAILABLE),
                    editor="number",
                    constraints={"min": asset.get("min_power_kw"), "max": asset.get("max_power_kw"), "step": 0.1},
                    operation_id="energy.property.write",
                    availability=asset.get("availability_state") or AVAILABLE,
                ),
                prop(aid, f"{aid}.operating_state", asset.get("operating_state"), availability=asset.get("availability_state") or AVAILABLE),
                prop(aid, f"{aid}.target_soc_pct", number(asset.get("target_soc_pct")), "%"),
                prop(aid, f"{aid}.current_soc_pct", number(asset.get("current_soc_pct")), "%"),
            ]
        )
    return assets, props


def _value_projection(meter: dict[str, Any], pricing_rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    price_by = by_key(pricing_rows)
    import_price = number((price_by.get("pricing.import_price_current_eur_kwh") or {}).get("value"))
    export_price = number((price_by.get("pricing.export_price_current_eur_kwh") or {}).get("value"))
    imp = number(meter.get("grid_import_kwh")); exp = number(meter.get("grid_export_kwh"))
    complete = None not in (import_price, export_price, imp, exp)
    import_cost = round(imp * import_price, 4) if complete else None
    export_revenue = round(exp * export_price, 4) if complete else None
    net = round(export_revenue - import_cost, 4) if complete else None
    availability = AVAILABLE if complete else CONFIGURATION_REQUIRED
    rows = [
        prop("value", "value.grid_import_cost_eur", import_cost, "EUR", availability=availability),
        prop("value", "value.grid_export_revenue_eur", export_revenue, "EUR", availability=availability),
        prop("value", "value.net_energy_value_eur", net, "EUR", availability=availability),
    ]
    summary = {
        "grid_import_kwh": imp,
        "grid_export_kwh": exp,
        "import_price_eur_kwh": import_price,
        "export_price_eur_kwh": export_price,
        "import_cost_eur": import_cost,
        "export_revenue_eur": export_revenue,
        "net_energy_value_eur": net,
        "completeness": "COMPLETE" if complete else "INCOMPLETE",
    }
    return availability, rows, summary


def _asset_row(
    asset_id: str,
    asset_type: str,
    display_name: str,
    property_index: str,
    availability: str,
    *,
    ux_asset_type: str | None = None,
    asset_role: str = "logical_singleton",
    cluster_role: str = "supporting_index",
    parent_asset_id: str | None = None,
    show_in_primary_ux: bool = True,
    show_in_engineering: bool = True,
    source_domain: str = "energy",
    capabilities: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Return the stable R1.84.2 asset-navigation shape from V2 truth.

    These rows are structural product metadata, not runtime placeholders.  An
    unavailable physical capability remains visible with an explicit
    availability state so the UX never has to guess from an asset id.
    """
    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "ux_asset_type": ux_asset_type or asset_type,
        "asset_role": asset_role,
        "cluster_role": cluster_role,
        "parent_asset_id": parent_asset_id,
        "display_name": display_name,
        "property_index": property_index,
        "show_in_primary_ux": show_in_primary_ux,
        "show_in_engineering": show_in_engineering,
        "source_domain": source_domain,
        "availability": availability,
        "capabilities": capabilities or [],
        **extra,
    }


def _assets(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    facts = snapshot.get("facts") or {}
    units = snapshot.get("battery_units") or []
    flexible = snapshot.get("flexible_assets") or []
    out = [
        _asset_row("solar", "solar", "Solar", "sensor.energy_solar_property_index", AVAILABLE if facts.get("solar.power_kw") is not None else UNAVAILABLE, asset_role="aggregate_parent", cluster_role="primary_cluster", capabilities=["power", "energy_today", "forecast_link"]),
        _asset_row("grid", "grid", "Grid", "sensor.energy_grid_property_index", AVAILABLE if facts.get("grid.net_power_kw") is not None else UNAVAILABLE, asset_role="aggregate_parent", cluster_role="primary_cluster", capabilities=["net_power", "import_power", "export_power", "import_energy", "export_energy"]),
        _asset_row("battery", "battery", "Home Battery", "sensor.energy_battery_property_index", AVAILABLE if facts.get("battery.soc_pct") is not None else UNAVAILABLE, asset_role="aggregate_parent", cluster_role="primary_cluster", capabilities=["power", "soc", "capacity", "available_energy", "reserve_soc"]),
        _asset_row("consumption", "consumption", "Consumption", "sensor.energy_consumption_property_index", AVAILABLE if facts.get("home_consumption.power_kw") is not None else UNAVAILABLE, asset_role="aggregate_parent", cluster_role="primary_cluster", capabilities=["power", "period_energy", "demand_breakdown"]),
        _asset_row("forecast", "forecast", "Forecast", "sensor.energy_forecast_property_index", AVAILABLE if facts.get("forecast.solar_today_kwh") is not None else UNAVAILABLE, asset_role="aggregate_parent", cluster_role="primary_cluster", capabilities=["solar_today", "solar_remaining_today", "solar_tomorrow"]),
        _asset_row("pricing", "pricing", "Pricing", "sensor.energy_pricing_property_index", AVAILABLE if facts.get("pricing.spot_eur_kwh") is not None else CONFIGURATION_REQUIRED, capabilities=["spot_price", "tariff_components", "derived_import_export_price"]),
        _asset_row("intelligence", "intelligence", "Energy Intelligence", "sensor.energy_intelligence_property_index", AVAILABLE if snapshot.get("intelligence") else UNAVAILABLE, cluster_role="operational_index", capabilities=["decision", "recommendation", "reason", "trust"]),
        _asset_row("outlook", "outlook", "Energy Outlook", "sensor.energy_outlook_property_index", AVAILABLE if snapshot.get("plan") else UNAVAILABLE, cluster_role="operational_index", parent_asset_id="intelligence", capabilities=["D0", "D1", "buckets"]),
        _asset_row("planning", "planning", "Energy Planning", "sensor.energy_planning_index", AVAILABLE if snapshot.get("plan") else UNAVAILABLE, cluster_role="operational_index", capabilities=["D0", "D1", "advisory_lanes", "allocations"]),
        _asset_row("activity", "activity", "Energy Activity", "sensor.energy_activity_index", AVAILABLE, cluster_role="operational_index", capabilities=["planning", "intelligence", "execution_audit"]),
        _asset_row("strategy_profile", "strategy_profile", "Energy Strategy Profiles", "sensor.energy_strategy_profile_index", AVAILABLE, cluster_role="policy_index", capabilities=["configured_policy"]),
        _asset_row("strategy_effective", "strategy_effective", "Effective Energy Strategy", "sensor.energy_strategy_effective_index", AVAILABLE, cluster_role="policy_resolution_index", parent_asset_id="strategy_profile", show_in_primary_ux=False, capabilities=["effective_policy"]),
        _asset_row("metering", "metering", "Metering", "sensor.energy_metering_property_index", AVAILABLE, asset_role="property_group", cluster_role="engineering_group", show_in_primary_ux=False, capabilities=["today", "iso_week", "month", "year", "per_flexible_asset"]),
        _asset_row("consumer", "consumer", "Consumers", "sensor.energy_consumer_property_index", AVAILABLE if flexible else UNAVAILABLE, ux_asset_type="consumer_cluster", asset_role="aggregate_parent", cluster_role="primary_cluster", capabilities=["power", "energy_need", "availability"]),
    ]
    for unit in units:
        aid = str(unit.get("asset_id") or "")
        if not aid:
            continue
        out.append(_asset_row(aid, "battery", unit.get("display_name") or aid.replace("_", " ").title(), "sensor.energy_battery_property_index", AVAILABLE if unit.get("health") == "OK" else UNAVAILABLE, ux_asset_type="battery_unit", asset_role="contributor_child", cluster_role="contributor_detail", parent_asset_id="battery", show_in_primary_ux=False, capabilities=["power", "soc", "capacity", "available_energy"]))
    for item in flexible:
        aid = str(item.get("asset_id") or "")
        if not aid:
            continue
        caps = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
        command_refs = item.get("command_refs") if isinstance(item.get("command_refs"), dict) else {}
        out.append(_asset_row(aid, "consumer", item.get("display_name") or aid.replace("_", " ").title(), "sensor.energy_consumer_property_index", item.get("availability_state") or AVAILABLE, ux_asset_type=item.get("ux_asset_type") or item.get("asset_type") or "flexible_load", asset_role="energy_consumer", cluster_role="contributor_detail", parent_asset_id="consumer", source_domain=item.get("source_domain") or "mobility", capabilities=sorted(set([str(k) for k in caps.keys()] + [str(k) for k in command_refs.keys()])), energy_asset_class=item.get("energy_asset_class") or "generic_flexible_load"))

    # E0.9.0 object-centric expansion.  The stable R1.84.2 aggregate rows above stay
    # untouched; logical V2 objects are additive children so existing YAML/Lovelace
    # consumers keep the exact outside contract while Home Assistant can navigate the
    # real object classes and properties behind it.
    existing = {str(row.get("asset_id")) for row in out}
    property_index_by_class = {
        "battery_system": "sensor.energy_battery_property_index",
        "battery_unit": "sensor.energy_battery_property_index",
        "grid_connection": "sensor.energy_grid_property_index",
        "solar_production": "sensor.energy_solar_property_index",
        "solar_inverter": "sensor.energy_solar_property_index",
        "solar_forecast": "sensor.energy_forecast_property_index",
        "price_source": "sensor.energy_pricing_property_index",
        "gas_meter": "sensor.energy_consumption_property_index",
        "solar_optimizer": "sensor.energy_solar_property_index",
        "home_consumption": "sensor.energy_consumption_property_index",
        "flexible_load": "sensor.energy_flexible_asset_index",
        "grid_phase": "sensor.energy_grid_property_index",
        "solar_inverter_phase": "sensor.energy_solar_property_index",
    }
    parent_by_class = {
        "battery_system": "battery", "battery_unit": "battery",
        "grid_connection": "grid", "solar_production": "solar",
        "solar_inverter": "solar", "solar_forecast": "forecast",
        "price_source": "pricing", "gas_meter": "consumption",
        "solar_optimizer": "solar",
        "home_consumption": "consumption",
        "flexible_load": "consumer",
        "grid_phase": "grid",
        "solar_inverter_phase": "solar",
    }
    for logical in snapshot.get("logical_assets") or []:
        if not isinstance(logical, dict):
            continue
        aid = str(logical.get("asset_id") or "")
        if not aid or aid in existing:
            continue
        object_class = str(logical.get("object_class") or logical.get("asset_type") or "logical_object")
        props = logical.get("properties") or []
        availability = AVAILABLE if any((row or {}).get("availability") == AVAILABLE for row in props if isinstance(row, dict)) else UNAVAILABLE
        out.append(_asset_row(
            aid,
            object_class,
            logical.get("display_name") or aid.replace("_", " ").title(),
            property_index_by_class.get(object_class, "sensor.energy_asset_index"),
            availability,
            ux_asset_type=object_class,
            asset_role="logical_object",
            cluster_role="contributor_detail",
            parent_asset_id=logical.get("parent_asset_id") or parent_by_class.get(object_class),
            show_in_primary_ux=bool(logical.get("runtime_truth")),
            show_in_engineering=True,
            capabilities=[str(row.get("property_key")) for row in props if isinstance(row, dict) and row.get("property_key")],
            logical_object_class=object_class,
            normalization_status=logical.get("normalization_status"),
            runtime_truth=bool(logical.get("runtime_truth")),
            integration_domain=logical.get("integration_domain"),
            property_count=len(props),
            available_property_count=int(logical.get("available_property_count") or 0),
        ))
        existing.add(aid)
    return out


def _relationships(snapshot: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def row(rid: str, source: str, target: str, rel_type: str, *, active: bool = True, **extra: Any) -> dict[str, Any]:
        return {
            "relationship_id": rid,
            "from_asset_id": source,
            "to_asset_id": target,
            "source_asset_id": source,
            "target_asset_id": target,
            "relationship_type": rel_type,
            "active": active,
            **extra,
        }
    rows = [
        row("solar_to_home", "solar", "consumption", "supplies"),
        row("grid_to_home", "grid", "consumption", "supplies_import"),
        row("home_to_grid", "consumption", "grid", "exports_via"),
        row("battery_to_home", "battery", "consumption", "supplies_or_absorbs"),
    ]
    for a in assets:
        if a.get("parent_asset_id"):
            rows.append(row(f"contains:{a['parent_asset_id']}:{a['asset_id']}", str(a["parent_asset_id"]), str(a["asset_id"]), "contains", active=a.get("availability") != UNSUPPORTED))
    for i, rel in enumerate(snapshot.get("connections") or []):
        if not isinstance(rel, dict):
            continue
        source = rel.get("source_asset_id") or rel.get("from_asset_id") or rel.get("source")
        target = rel.get("target_asset_id") or rel.get("to_asset_id") or rel.get("target")
        if source and target:
            rows.append(row(str(rel.get("relationship_id") or f"mobility:{i}"), str(source), str(target), str(rel.get("relationship_type") or rel.get("type") or "connected_to"), active=bool(rel.get("active", True)), **{k: deepcopy(v) for k, v in rel.items() if k not in {"relationship_id","source_asset_id","from_asset_id","source","target_asset_id","to_asset_id","target","relationship_type","type","active"}}))
    return rows


def project_all(snapshot: dict[str, Any], store_data: dict[str, Any], command_rows: list[dict[str, Any]], manager: Any) -> dict[str, dict[str, Any]]:
    """Return object_id -> {state, attributes} for the complete legacy surface."""
    snap = deepcopy(snapshot)
    snap["settings"] = deepcopy(store_data.get("settings") or {})
    model = getattr(manager, "compiled_model", None) or {}
    concepts = model.get("concepts") or {}
    battery_system = concepts.get("battery_system") or {}
    snap["battery_reserve_write_supported"] = bool(battery_system.get("reserve_binding"))
    facts = snap.get("facts") or {}
    rows = _fact_rows(snap)
    meter_status, meter_ctx, meter_props = _metering_projection(store_data)
    # Preserve the legacy consumption/solar property vocabulary using V2-owned
    # metering/forecast truth.  Unknown lifetime consumption remains explicit
    # rather than being fabricated from an incomplete period.
    today_meter = (meter_ctx.get("periods_by_id") or {}).get("today") or {}
    rows["consumption"].extend([
        prop("consumption", "consumption.today_kwh", number(today_meter.get("consumption_kwh")), "kWh", source_type="metering"),
        prop("consumption", "consumption.total_kwh", number(facts.get("metering.consumption_total_kwh")), "kWh", availability=AVAILABLE if facts.get("metering.consumption_total_kwh") is not None else INCOMPLETE, source_type="metering", reason_code=None if facts.get("metering.consumption_total_kwh") is not None else "lifetime_consumption_not_proven"),
    ])
    solar_today = number(facts.get("solar.energy_today_kwh"))
    solar_forecast = number(facts.get("forecast.solar_today_kwh"))
    rows["solar"].extend([
        prop("solar", "solar.today_kwh", solar_today, "kWh"),
        prop("solar", "solar.forecast_kwh", solar_forecast, "kWh", source_type="forecast", quality="forecast"),
    ])
    flex_assets, flex_props = _flexible_projection(snap, command_rows)
    assets = _assets(snap)
    relationships = _relationships(snap, assets)
    strategy_rows = rows["strategy"]
    pricing_rows = rows["pricing"]
    plan = snap.get("plan") or {}
    intel = snap.get("intelligence") or {}
    selected_period = meter_ctx["selected_period_id"]
    value_status, value_rows, value_summary = _value_projection(meter_ctx["selected"], pricing_rows)

    demand_breakdown = []
    home = number(facts.get("home_consumption.power_kw"))
    if home is not None:
        demand_breakdown.append({"asset_id":"home","label":"Home","power_kw":home,"availability":AVAILABLE})
    demand_breakdown.extend({"asset_id":a.get("asset_id"),"label":a.get("display_name"),"power_kw":a.get("power_kw"),"availability":a.get("availability_state") or AVAILABLE} for a in flex_assets)
    overview = overview_snapshot(facts, demand_breakdown)
    selected_flexible_kwh = deepcopy((meter_ctx["selected"].get("flexible_assets_kwh") or {}))
    for asset in flex_assets:
        asset["selected_period_id"] = selected_period
        asset["selected_period_energy_kwh"] = selected_flexible_kwh.get(str(asset.get("asset_id")))

    forecast_status = _status_for_rows(rows["forecast"])
    planning_horizons = plan.get("planning_horizons") or {}
    horizons_list = [planning_horizons[k] for k in ("D0","D1") if k in planning_horizons]
    planning_status = AVAILABLE if plan and horizons_list else UNAVAILABLE
    if plan.get("health") == "DEGRADED": planning_status = INCOMPLETE

    intelligence_rows = [
        prop("intelligence", "energy_intelligence.decision", intel.get("decision"), availability=intel.get("availability") or UNAVAILABLE),
        prop("intelligence", "energy_intelligence.recommendation", intel.get("recommendation"), availability=intel.get("availability") or UNAVAILABLE),
        prop("intelligence", "energy_intelligence.reason", intel.get("reason"), availability=intel.get("availability") or UNAVAILABLE),
        prop("intelligence", "energy_intelligence.trust", intel.get("trust"), availability=intel.get("availability") or UNAVAILABLE),
    ]
    planning_rows = [
        prop("planning", "planning.current_plan_id", plan.get("plan_id"), availability=planning_status),
        prop("planning", "planning.health", plan.get("health"), availability=planning_status),
    ]

    effective = []
    for r in strategy_rows:
        effective.append({
            "property_id": r.get("property_id"),
            "subdomain_id": r.get("group") or "home",
            "configured_value": r.get("value"),
            "effective_value": r.get("value"),
            "unit": r.get("unit"),
            "availability": r.get("availability"),
            "reason_code": None,
            "override_source": None,
            "editable": False,
        })
    strategies_by_asset = []
    for a in flex_assets:
        strategies_by_asset.append({
            "asset_id":a.get("asset_id"),"source_domain":a.get("source_domain") or "mobility","energy_asset_class":a.get("energy_asset_class") or "generic_flexible_load",
            "energy_operating_mode":(store_data.get("settings") or {}).get("strategy",{}).get("energy.operating_mode","advice"),
            "capabilities":{"min_power_kw":a.get("min_power_kw"),"max_power_kw":a.get("max_power_kw"),"write_capability":a.get("command_refs") or {}},
            "planning_owner":"sensor.energy_planning_index","command_owner":"sensor.energy_command_index","validation_state":"ready",
        })

    # Editable index contains only operations that are backed by real persistent
    # state or a real producer-owned execution path.
    editable = [r for r in pricing_rows + strategy_rows + meter_props + flex_props + rows["battery"] if r.get("editable") is True and (r.get("write") or {}).get("supported") is True]
    activities = deepcopy(store_data.get("activity") or [])
    activities.append({"at":plan.get("generated_at"),"activity_type":"planning","plan_id":plan.get("plan_id"),"status":plan.get("health")})
    if intel:
        activities.append({"at":plan.get("generated_at"),"activity_type":"intelligence","activity_state":intel.get("availability") or UNAVAILABLE,"status":intel.get("availability") or UNAVAILABLE,"decision":intel.get("decision"),"reason":intel.get("reason")})
    activities = [x for x in activities if isinstance(x, dict) and x.get("at")][-40:]

    projections: dict[str, dict[str, Any]] = {}
    public_list = list(LEGACY_PUBLIC_ENTITIES)
    projections["energy_release_contract"] = {
        "state":"ready",
        "attributes":{
            "contract_schema":"home_intelligence_release_contract_v1","domain":"energy","backend_release":RELEASE,"contract_version":LEGACY_CONTRACT_VERSION,
            "schema_version":1,"contract_health":"ready","canonical_release_source":"sensor.energy_release_contract","release_consistency_gate":"enabled",
            "frontend_expected_release_attribute":"backend_release","public_contract_model":"typed_family_indexes_under_lean_public_categories",
            "domain_semantics_policy":"backend_publishes_domain_contract_not_user_experience","ux_public_entities":jdump(public_list),"public_ux_entities_json":jdump(public_list),
            "outlook_contract_owner":"sensor.energy_outlook_property_index","planning_contract_owner":"sensor.energy_planning_index",
            "metering_period_selector_policy":"today_week_month_year_week_is_iso_calendar_week_no_tomorrow_metering",
            "public_contract_policy":"ux_compatible_v2_runtime_domain_owned_execution","runtime_proof_policy":"pilot_runtime_proof_required_before_production",
            "foundation_runtime_policy":"configuration_time_active_runtime_passive","legacy_yaml_runtime_required":False,"compatibility_source_release":"R1.84.2",
            "product_status":"AVAILABLE","product_reason":"V2 Python runtime publishes the R1.84.2 UX contract surface.",
        },
    }
    ov_state = AVAILABLE if overview.get("complete") else UNAVAILABLE
    ov_snap = overview
    overview_reason = "Core Energy facts are available." if ov_state == AVAILABLE else "Core Energy facts are unavailable."
    projections["energy_overview_experience"] = {"state":ov_state,"attributes":{**_base("overview_experience_v1_compatibility_preserved"),"status":ov_state,"reason":overview_reason,"product_status":ov_state,"product_reason":overview_reason,"snapshot_json":jdump(ov_snap),"summary_json":jdump(overview.get("summary") or {}),"flow_json":jdump(overview.get("flow") or {}),"summary":jdump(overview.get("summary") or {}),"conclusions":jdump(intelligence_rows[:3]),"ux_rule":"Render snapshot_json as the only Overview source; backend owns status and primary KPI."}}
    outlook_status = planning_status if planning_horizons else forecast_status
    outlook_reason = plan.get("reason") or ("backend_owned_d0_d1_horizons_available" if planning_horizons else "forecast_or_planning_evidence_unavailable")
    projections["energy_outlook_property_index"] = {"state":outlook_status,"attributes":{**_base("energy_outlook_property_index_v2_compat"),"index_type":"outlook_property_index","asset_type":"outlook","status":outlook_status,"reason":outlook_reason,"horizon_model":"D0_D1","graph_support":True,"bucket_support":True,"supported_horizons_json":jdump(["D0","D1"]),"horizons_json":jdump(horizons_list),"horizons_by_id":jdump(planning_horizons),"properties":jdump(rows["forecast"]+planning_rows),"properties_by_key":jdump(by_key(rows["forecast"]+planning_rows)),"health":"OK" if outlook_status==AVAILABLE else outlook_status,"health_reason":outlook_reason,"ux_rule":"Use backend-owned horizon summaries and buckets; do not recalculate totals."}}
    for name, key, schema in (
        ("energy_solar_property_index","solar","energy_solar_property_index_v2_compat"),
        ("energy_battery_property_index","battery","energy_battery_property_index_v2_compat"),
        ("energy_grid_property_index","grid","energy_grid_property_index_v2_compat"),
        ("energy_consumption_property_index","consumption","energy_consumption_property_index_v2_compat"),
        ("energy_forecast_property_index","forecast","energy_forecast_property_index_v2_compat"),
        ("energy_pricing_property_index","pricing","energy_pricing_property_index_v2_compat"),
    ):
        r = rows[key]
        extra={"index_type":"property_index","asset_type":key,"lookup_rule":"properties_by_key","iteration_rule":"properties"}
        if key=="battery": extra.update({"battery_bank_ids_json":jdump([u.get("asset_id") for u in snap.get("battery_units") or []]),"battery_banks_json":jdump(snap.get("battery_units") or [])})
        if key=="solar": extra.update({"forecast_source_index":"sensor.energy_forecast_property_index","forecast_property_keys_json":jdump(["forecast.solar_today_kwh","forecast.solar_remaining_today_kwh","forecast.solar_tomorrow_kwh"]),"forecast_linkage":"backend_owned_reference"})
        if key=="consumption": extra.update({"demand_export_contract":"backend_owned_breakdown","demand_export_iteration_attribute":"demand_export_breakdown_json","demand_export_breakdown_json":jdump(demand_breakdown),"period_energy_source":"sensor.energy_metering_property_index"})
        projections[name]={"state":_status_for_rows(r),"attributes":_property_attrs(r,schema,**extra)}

    projections["energy_metering_property_index"]={"state":meter_status,"attributes":{**_property_attrs(meter_props,"energy_metering_property_index_v2_compat",index_type="metering_property_index"),"selected_context_json":jdump({"type":"period","value":selected_period}),"selected_period_summary":jdump(meter_ctx["selected"]),"selected_period_properties":jdump(meter_props),"periods_json":jdump(meter_ctx["periods"]),"period_summary_by_id":jdump(meter_ctx["periods_by_id"]),"remediations_json":jdump([])}}
    consumer_props=[]
    for a in flex_assets:
        aid=a.get("asset_id"); consumer_props.extend([prop(aid,f"{aid}.power_kw",number(a.get("power_kw")),"kW"),prop(aid,f"{aid}.energy_to_target_kwh",number(a.get("energy_to_target_kwh")),"kWh"),prop(aid,f"{aid}.availability",a.get("availability_state") or AVAILABLE)])
    consumer_state=AVAILABLE if flex_assets else UNAVAILABLE
    projections["energy_consumer_property_index"]={"state":consumer_state,"attributes":_property_attrs(consumer_props,"energy_consumer_property_index_v2_compat",index_type="consumer_property_index")}
    total_flex=sum(number(a.get("power_kw")) or 0.0 for a in flex_assets) if flex_assets else 0.0
    known_need=[number(a.get("energy_to_target_kwh")) for a in flex_assets if number(a.get("energy_to_target_kwh")) is not None]
    today_flexible = (((meter_ctx.get("periods_by_id") or {}).get("today") or {}).get("flexible_assets_kwh") or {})
    pricing_available = _status_for_rows(pricing_rows) == AVAILABLE
    mix_assets=[]
    for a in flex_assets:
        aid=str(a.get("asset_id") or "")
        mix_assets.append({
            "asset_id":aid,
            "display_name":a.get("display_name") or aid.replace("_"," ").title(),
            "category":a.get("asset_type") or "other",
            "controllability":"FLEXIBLE",
            "current_power_kw":number(a.get("power_kw")),
            "energy_today_kwh":number(today_flexible.get(aid)),
            "energy_need_kwh":number(a.get("energy_to_target_kwh")),
            "availability":a.get("availability_state") or AVAILABLE,
            "source_attribution":{"solar_kwh":None,"grid_kwh":None,"battery_kwh":None,"availability":INCOMPLETE},
            "cost_attribution":{"amount_eur":None,"availability":INCOMPLETE if pricing_available else CONFIGURATION_REQUIRED},
        })
    mix_summary={
        "current_power_kw":round(total_flex,4) if flex_assets else None,
        "known_energy_need_kwh":round(sum(known_need),4) if known_need else None,
        "asset_count":len(flex_assets),
        "availability":consumer_state,
        "source_attribution_availability":INCOMPLETE,
        "cost_attribution_availability":INCOMPLETE if pricing_available else CONFIGURATION_REQUIRED,
        "selected_period_id":selected_period,
        "energy_kwh":meter_ctx["selected"].get("flexible_load_kwh"),
        "energy_by_asset_kwh":selected_flexible_kwh,
        "energy_attribution":"measured_by_energy_runtime",
    }
    projections["energy_consumer_mix_index"]={"state":consumer_state,"attributes":{**_base("energy_consumer_mix_index_v2_compat"),"index_type":"consumer_mix_index","ownership_policy":"Energy aggregates producer-domain public assets without owning physical targets.","availability":consumer_state,"source_attribution_availability":INCOMPLETE,"cost_attribution_availability":INCOMPLETE if pricing_available else CONFIGURATION_REQUIRED,"context_json":jdump({"type":"period","value":selected_period}),"summary_json":jdump(mix_summary),"assets_json":jdump(mix_assets)}}
    projections["energy_flexible_asset_index"]={"state":consumer_state,"attributes":{**_property_attrs(flex_props,"energy_flexible_asset_index_v2_compat"),"projection_schema":"energy_flexible_asset_projection_v2","source_of_truth":"sensor.mobility_energy_asset_publication","source_entities_json":jdump(["sensor.mobility_energy_asset_publication"]),"primary_iteration_attribute":"assets_json","assets_json":jdump(flex_assets),"command_state_source":"sensor.energy_command_index","canonical_mobility_source":"sensor.mobility_energy_asset_publication","health":"OK" if consumer_state==AVAILABLE else consumer_state}}
    projections["energy_strategy_profile_index"]={"state":AVAILABLE,"attributes":{**_property_attrs(strategy_rows,"energy_strategy_profile_index_v2_compat",index_type="strategy_profile_index"),"configured_operating_mode":(store_data.get("settings") or {}).get("strategy",{}).get("energy.operating_mode","advice"),"energy_operating_mode_value":(store_data.get("settings") or {}).get("strategy",{}).get("energy.operating_mode","advice"),"energy_operating_mode":(store_data.get("settings") or {}).get("strategy",{}).get("energy.operating_mode","advice"),"profiles_json":jdump([{"profile_id":"configured","properties":strategy_rows}]),"profiles_by_id_json":jdump({"configured":{"profile_id":"configured","properties":strategy_rows}}),"published_profile_count":1,"properties_json":jdump(strategy_rows),"product_status":AVAILABLE,"product_reason":"Persistent V2 strategy configuration is available."}}
    projections["energy_strategy_effective_index"]={"state":AVAILABLE,"attributes":{**_base("energy_strategy_effective_index_v2_compat"),"ownership_boundary":"configured_intent_is_strategy_effective_values_are_read_only","editable":False,"editable_source":"sensor.energy_strategy_profile_index","effective_strategies_json":jdump(strategies_by_asset),"strategies_by_asset_id_json":jdump({r["asset_id"]:r for r in strategies_by_asset}),"effective_subdomains_json":jdump(effective),"current_policies_json":jdump(effective),"configured_strategy_owner":"sensor.energy_strategy_profile_index","effective_property_rule":"effective values are read-only policy resolution; never commands"}}
    projections["energy_planning_index"]={"state":planning_status,"attributes":{**_property_attrs(planning_rows,"energy_planning_index_v2_compat",index_type="planning_index",asset_type="planning"),"planning_owner":"rhi_energy","planning_schema_version":2,"plan_id":plan.get("plan_id"),"commit_reason":plan.get("reason"),"planning_horizons_json":jdump(horizons_list),"planning_horizons_by_id":jdump(planning_horizons),"planning_horizon_count":len(horizons_list),"planning_lane_contract":"summary.lane_totals is authoritative","timeline_scope":"D0_remaining_today_D1_full_day_estimated_buckets","health":plan.get("health") or UNAVAILABLE,"health_reason":plan.get("reason") or "planning_unavailable"}}
    p_summary={"plan_id":plan.get("plan_id"),"health":plan.get("health"),"decision":intel.get("decision"),"recommendation":intel.get("recommendation"),"next_actions":[intel.get("recommendation")] if intel.get("recommendation") else []}
    p_assets=[{"asset_id":a.get("asset_id"),"display_name":a.get("display_name"),"energy_to_target_kwh":a.get("energy_to_target_kwh"),"planning_hold":a.get("planning_hold",False)} for a in flex_assets]
    projections["energy_planning_experience_index"]={"state":planning_status,"attributes":{**_base("energy_planning_experience_index_v2_compat"),"ux_rule":"Render backend planning summaries and next actions; do not infer readiness.","health":plan.get("health") or UNAVAILABLE,"health_reason":plan.get("reason") or "planning_unavailable","assets_json":jdump(p_assets),"summary_json":jdump(p_summary)}}
    projections["energy_command_index"]={"state":AVAILABLE if command_rows else UNAVAILABLE,"attributes":{**_base("energy_command_index_v2_compat"),"index_type":"command_index","commands_json":jdump(command_rows),"commands":jdump(command_rows),"command_count":len(command_rows),"execution_owner":"rhi_energy","physical_target_owner":"producer_domain"}}
    projections["energy_intelligence_property_index"]={"state":intel.get("availability") or UNAVAILABLE,"attributes":{**_property_attrs(intelligence_rows,"energy_intelligence_property_index_v2_compat",index_type="intelligence_property_index",asset_type="intelligence"),"intelligence_model":"deterministic_capacity_aware_v1","decision_contract":"backend_owned","current_decision_json":jdump(intel),"influencing_policies_json":jdump(effective),"configured_not_relevant_policies_json":jdump([]),"scheduler_contract":"planning_and_execution_separated"}}
    flexible_value_rows=[]
    for asset in flex_assets:
        aid=str(asset.get("asset_id"))
        measured=number(selected_flexible_kwh.get(aid))
        flexible_value_rows.append({"asset_id":aid,"display_name":asset.get("display_name"),"period_id":selected_period,"measured_energy_kwh":measured,"quantity_status":AVAILABLE if measured is not None else INCOMPLETE,"energy_cost_eur":None,"energy_value_eur":None,"financial_attribution_status":INCOMPLETE,"reason":"measured_quantity_available_but_source_cost_attribution_not_proven" if measured is not None else "per_asset_metering_not_available"})
    projections["energy_value_accounting_index"]={"state":value_status,"attributes":{**_base("energy_value_accounting_index_v2_compat"),"index_type":"value_accounting_index","period_owner":"sensor.energy_metering_property_index","selected_period_entity":"sensor.energy_metering_property_index","selected_context_json":jdump({"type":"period","value":selected_period}),"billing_in_scope":False,"missing_value_policy":"null_plus_CONFIGURATION_REQUIRED","quantity_owner":"metering","quantity_source_index":"sensor.energy_metering_property_index","tariff_owner":"pricing","tariff_source_index":"sensor.energy_pricing_property_index","rows_json":jdump(value_rows),"rows_by_key":jdump(by_key(value_rows)),"tariff_breakdown_json":jdump(pricing_rows),"summary_json":jdump(value_summary),"product_status_json":jdump({"status":value_status,"reason":"complete_tariff_and_quantity_evidence" if value_status==AVAILABLE else "tariff_or_quantity_configuration_incomplete"}),"status":value_status,"status_label":"Available" if value_status==AVAILABLE else "Configuration required","flexible_asset_value_json":jdump(flexible_value_rows),"health":"OK" if value_status==AVAILABLE else value_status}}
    projections["energy_asset_index"]={"state":AVAILABLE if assets else UNAVAILABLE,"attributes":{**_base("energy_asset_index_v2_compat"),"registry_type":"energy_asset_index","lifecycle_stage":"runtime","normalized_vocabulary":"properties_capabilities_commands","asset_contract_schema":"energy_asset_index_v2_model_authoritative_visibility","required_asset_fields_json":jdump(["asset_id","asset_type","ux_asset_type","asset_role","cluster_role","show_in_primary_ux","show_in_engineering","property_index"]),"visibility_contract":"model_authoritative_no_ux_guessing_from_asset_id","assets_json":jdump(assets),"public_contract_model":"canonical_assets","asset_model":"domain_and_external_publication","canonical_mobility_source":"sensor.mobility_energy_asset_publication"}}
    projections["energy_relationship_index"]={"state":AVAILABLE,"attributes":{**_base("energy_relationship_index_v2_compat"),"index_type":"relationship_index","source_registry":"sensor.energy_asset_index","relationships":jdump(relationships),"relationships_by_id":jdump({str(r.get("relationship_id")):r for r in relationships})}}
    projections["energy_activity_index"]={"state":AVAILABLE,"attributes":{**_base("energy_activity_index_v2_compat"),"index_type":"activity_index","activity_model":"bounded_v2_runtime_activity","activities":jdump(activities),"activities_by_id":jdump({f"activity:{i}":r for i,r in enumerate(activities)}),"health":"OK","health_reason":"persistent bounded activity evidence"}}
    projections["energy_public_editable_property_index"]={"state":AVAILABLE,"attributes":{**_base("energy_public_editable_property_index_v2_compat"),"lifecycle":"canonical","safe_to_retire":False,"replacement":"domain_owned_property_indexes","properties":jdump(editable),"properties_json":jdump(editable),"properties_by_key":jdump(by_key(editable)),"editable_property_count":len(editable)}}
    return projections


class PublicContractProjector:
    """Cache public projections and notify only entities whose payload changed."""
    def __init__(self, runtime: Any, store: Any, metering: Any, interaction: Any, manager: Any) -> None:
        self.runtime=runtime; self.store=store; self.metering=metering; self.interaction=interaction; self.manager=manager
        self._cache: dict[str,dict[str,Any]]={}; self._callbacks: dict[str,list[Callable[[],None]]]={}; self._removers=[]

    def start(self) -> None:
        for owner in (self.runtime,self.store,self.metering,self.interaction,self.manager):
            if hasattr(owner,"add_callback"):
                self._removers.append(owner.add_callback(self.recompute))
        self.recompute()

    def add_callback(self,object_id: str, cb: Callable[[],None]) -> Callable[[],None]:
        self._callbacks.setdefault(object_id,[]).append(cb)
        def remove():
            rows=self._callbacks.get(object_id,[])
            if cb in rows: rows.remove(cb)
        return remove

    def get(self, object_id: str) -> dict[str,Any]:
        return deepcopy(self._cache.get(object_id) or {"state":UNAVAILABLE,"attributes":_base("unavailable")})

    def recompute(self) -> None:
        # Add structural evidence that belongs to runtime/model without putting
        # Foundation into the measurement fast path.
        snapshot=deepcopy(self.runtime.snapshot)
        model=self.manager.compiled_model or {}
        bsys=(model.get("concepts") or {}).get("battery_system") or {}
        reserve_id=bsys.get("reserve_binding")
        snapshot["battery_reserve_write_supported"]=bool(reserve_id)
        snapshot["settings"]=deepcopy(self.store.data.get("settings") or {})
        new=project_all(snapshot,self.store.data,self.interaction.command_rows(),self.manager)
        for oid,payload in new.items():
            if payload != self._cache.get(oid):
                self._cache[oid]=payload
                for cb in tuple(self._callbacks.get(oid,[])): cb()

    async def async_stop(self) -> None:
        for remove in self._removers:
            if callable(remove): remove()
        self._removers=[]; self._callbacks={}
