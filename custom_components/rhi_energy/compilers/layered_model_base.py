"""Deterministic layered Energy model materialization.

Compile owns topology. Runtime may update values but may never discover, add, remove or
re-parent concepts. Compatibility remains downstream of this canonical graph.
"""
from __future__ import annotations
import hashlib, json
from typing import Any


def _node(asset_id: str, concept_id: str, layer: str, *, status: str = "READY", sources=(), reason=None):
    row = {"asset_id": asset_id, "concept_id": concept_id, "layer": layer, "owner": "rhi_energy", "status": status, "source_asset_ids": sorted(set(sources))}
    if reason:
        row["reason"] = reason
    return row


def _edge(source: str, target: str, kind: str, criticality: str = "REQUIRED"):
    return {"from": source, "to": target, "dependency_type": kind, "criticality": criticality}


def _assets(model: dict[str, Any], object_class: str) -> list[str]:
    return [str(x["asset_id"]) for x in model.get("logical_assets") or [] if isinstance(x, dict) and x.get("asset_id") and x.get("object_class") == object_class]


def _logical(model: dict[str, Any]) -> list[dict[str, Any]]:
    aggregates = {"battery_system", "solar_production", "home_consumption", "flexible_load"}
    return [_node(str(x["asset_id"]), str(x.get("object_class") or "unknown"), "logical", status="READY" if x.get("normalization_status") == "READY" else "DEGRADED") for x in model.get("logical_assets") or [] if isinstance(x, dict) and x.get("asset_id") and x.get("object_class") not in aggregates]


def _systems(model: dict[str, Any]):
    edges = []
    battery_units = _assets(model, "battery_unit")
    legacy_battery = _assets(model, "battery_system")
    battery_id = legacy_battery[0] if legacy_battery else "battery_system:home"
    inverters = _assets(model, "solar_inverter")
    legacy_solar = _assets(model, "solar_production")
    solar_id = legacy_solar[0] if legacy_solar else "solar_production:home"
    grids = _assets(model, "grid_connection")
    grid_id = grids[0] if grids else None
    forecasts = _assets(model, "solar_forecast")
    prices = _assets(model, "price_source")
    systems = [
        _node(battery_id, "battery_system", "system", status="READY" if battery_units else "INCOMPLETE", sources=battery_units, reason=None if battery_units else "battery_units_unavailable"),
        _node(solar_id, "solar_production_system", "system", status="READY" if inverters else "INCOMPLETE", sources=inverters, reason=None if inverters else "solar_inverters_unavailable"),
        _node("site_energy_balance:home", "site_energy_balance", "system", status="READY" if grid_id and inverters else "INCOMPLETE", sources=[x for x in (solar_id, battery_id, grid_id) if x], reason=None if grid_id and inverters else "required_balance_inputs_incomplete"),
        _node("home_consumption:home", "home_consumption", "system", status="READY" if grid_id and inverters else "INCOMPLETE", sources=["site_energy_balance:home"]),
        _node("solar_forecast_system:home", "solar_forecast_system", "system", status="READY" if forecasts else "INCOMPLETE", sources=forecasts, reason=None if forecasts else "forecast_source_unavailable"),
        _node("pricing_system:home", "pricing_system", "system", status="READY" if prices else "INCOMPLETE", sources=prices, reason=None if prices else "price_source_unavailable"),
        _node("flexible_load_system:home", "flexible_load_system", "system", status="INCOMPLETE", reason="producer_inventory_runtime_bound"),
        _node("connection_system:home", "connection_system", "system", status="INCOMPLETE", reason="producer_inventory_runtime_bound"),
        _node("metering_system:home", "metering_system", "system", sources=["site_energy_balance:home"]),
        _node("strategy_system:home", "strategy_system", "system"),
        _node("value_accounting_system:home", "value_accounting_system", "system", status="INCOMPLETE", sources=["metering_system:home", "pricing_system:home"], reason="counterfactual_value_not_evaluated"),
    ]
    for source in battery_units: edges.append(_edge(source, battery_id, "aggregate_member"))
    for source in inverters: edges.append(_edge(source, solar_id, "aggregate_member"))
    for source in [x for x in (solar_id, battery_id, grid_id) if x]: edges.append(_edge(source, "site_energy_balance:home", "balance_input", "OPTIONAL" if source == battery_id else "REQUIRED"))
    edges += [_edge("site_energy_balance:home", "home_consumption:home", "derived_fact"), _edge("site_energy_balance:home", "metering_system:home", "metering_input"), _edge("metering_system:home", "value_accounting_system:home", "accounting_input"), _edge("pricing_system:home", "value_accounting_system:home", "accounting_input")]
    for source in forecasts: edges.append(_edge(source, "solar_forecast_system:home", "semantic_source"))
    for source in prices: edges.append(_edge(source, "pricing_system:home", "semantic_source"))
    return systems, edges, battery_id


def _planning(battery_id: str):
    rows = [
        _node("planning_model:home", "planning_model", "planning"),
        _node("planning_horizon:D0", "planning_horizon", "planning"), _node("planning_horizon:D1", "planning_horizon", "planning"),
        _node("planning_supply:solar", "planning_supply", "planning", sources=["solar_forecast_system:home"]),
        _node("planning_supply:grid", "planning_supply", "planning", sources=["site_energy_balance:home"]),
        _node("planning_storage:battery", "planning_asset", "planning", sources=[battery_id]),
        _node("planning_demand:home", "planning_demand", "planning", sources=["home_consumption:home"]),
        _node("planning_demand:flexible", "planning_demand", "planning", status="INCOMPLETE", sources=["flexible_load_system:home"], reason="producer_inventory_runtime_bound"),
        _node("planning_pricing:home", "planning_pricing", "planning", sources=["pricing_system:home"]),
        _node("constraint_set:site", "constraint_set", "planning", sources=["strategy_system:home"]),
        _node("energy_need:flexible", "energy_need", "planning", status="INCOMPLETE", sources=["flexible_load_system:home"]),
        _node("allocation_set:operational", "allocation_set", "planning", status="INCOMPLETE", reason="planner_evaluation_required"),
    ]
    edges = [_edge("planning_model:home", h, "contains") for h in ("planning_horizon:D0", "planning_horizon:D1")]
    inputs = ["planning_supply:solar", "planning_supply:grid", "planning_storage:battery", "planning_demand:home", "planning_demand:flexible", "planning_pricing:home", "constraint_set:site", "energy_need:flexible"]
    for h in ("planning_horizon:D0", "planning_horizon:D1"):
        edges += [_edge(x, h, "planning_input", "QUALITY_ENHANCING" if x in {"planning_demand:flexible", "energy_need:flexible"} else "REQUIRED") for x in inputs]
        edges.append(_edge(h, "allocation_set:operational", "allocation_input"))
    edges += [_edge("solar_forecast_system:home", "planning_supply:solar", "planning_projection"), _edge("site_energy_balance:home", "planning_supply:grid", "planning_projection"), _edge(battery_id, "planning_storage:battery", "planning_projection"), _edge("home_consumption:home", "planning_demand:home", "planning_projection"), _edge("flexible_load_system:home", "planning_demand:flexible", "planning_projection"), _edge("flexible_load_system:home", "energy_need:flexible", "planning_projection"), _edge("pricing_system:home", "planning_pricing:home", "planning_projection"), _edge("strategy_system:home", "constraint_set:site", "planning_projection")]
    return rows, edges


def _intelligence():
    rows = [_node("operational_plan:home", "operational_plan", "intelligence", status="INCOMPLETE"), _node("energy_outlook:home", "energy_outlook", "intelligence", status="INCOMPLETE"), _node("cost_outlook:home", "cost_outlook", "intelligence", status="INCOMPLETE"), _node("resilience_state:home", "resilience_state", "intelligence", status="INCOMPLETE"), _node("optimization_opportunity:home", "optimization_opportunity", "intelligence", status="INCOMPLETE"), _node("energy_intelligence:home", "energy_intelligence", "intelligence", status="INCOMPLETE"), _node("planning_experience:home", "planning_experience", "intelligence", status="INCOMPLETE")]
    edges = [_edge("allocation_set:operational", "operational_plan:home", "intelligence_input"), _edge("operational_plan:home", "energy_outlook:home", "outlook_input"), _edge("solar_forecast_system:home", "energy_outlook:home", "outlook_input"), _edge("pricing_system:home", "cost_outlook:home", "outlook_input"), _edge("operational_plan:home", "cost_outlook:home", "outlook_input"), _edge("strategy_system:home", "resilience_state:home", "resilience_input"), _edge("energy_outlook:home", "energy_intelligence:home", "intelligence_input"), _edge("cost_outlook:home", "energy_intelligence:home", "intelligence_input"), _edge("resilience_state:home", "energy_intelligence:home", "intelligence_input"), _edge("energy_intelligence:home", "optimization_opportunity:home", "opportunity_input"), _edge("operational_plan:home", "planning_experience:home", "experience_input"), _edge("energy_intelligence:home", "planning_experience:home", "experience_input")]
    return rows, edges


def materialize_layered_energy_model(model: dict[str, Any]) -> dict[str, Any]:
    logical = _logical(model); systems, se, battery_id = _systems(model); planning, pe = _planning(battery_id); intelligence, ie = _intelligence(); dependencies = se + pe + ie
    node_ids = {str(x["asset_id"]) for group in (logical, systems, planning, intelligence) for x in group}
    basis = {"logical": logical, "system": systems, "planning": planning, "intelligence": intelligence, "dependencies": dependencies}
    fingerprint = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    return {"layer_contract_version": "1.0.0", "logical_layer": logical, "system_assets": systems, "planning_assets": planning, "intelligence_assets": intelligence, "dependencies": dependencies, "model_fingerprint": fingerprint, "dependency_diagnostics": {"node_count": len(node_ids), "edge_count": len(dependencies), "missing_source_nodes": sorted({e["from"] for e in dependencies if e["from"] not in node_ids})}, "runtime_rules": {"runtime_may_mutate_topology": False, "runtime_may_discover_assets": False, "telemetry_may_trigger_compile": False, "structural_changes_require_new_generation": True, "compatibility_projection_may_create_semantics": False}}
