"""Finalize the active Energy graph after additive layer closure."""
from __future__ import annotations

import hashlib
import json


def _health(rows):
    states = {
        str(row.get("status") or "INCOMPLETE")
        for row in rows
        if isinstance(row, dict)
    }
    if states and states == {"READY"}:
        return "OK"
    if "READY" in states:
        return "DEGRADED"
    return "INCOMPLETE"


def finalize_layered_energy_model(layered):
    logical = list(layered.get("logical_layer") or [])
    systems = list(layered.get("system_assets") or [])
    planning = list(layered.get("planning_assets") or [])
    intelligence = list(layered.get("intelligence_assets") or [])
    dependencies = list(layered.get("dependencies") or [])

    system_by_concept = {
        str(row.get("concept_id")): row
        for row in systems
        if isinstance(row, dict)
    }
    balance_ready = (
        (system_by_concept.get("site_energy_balance") or {}).get("status") == "READY"
    )
    grid = system_by_concept.get("grid_system")
    if grid is not None and not balance_ready:
        grid["status"] = "INCOMPLETE"
        grid["reason"] = "site_energy_balance_incomplete"

    baseline_ready = all(
        (system_by_concept.get(concept) or {}).get("status") == "READY"
        for concept in ("solar_forecast_system", "home_consumption")
    )
    for row in planning:
        if isinstance(row, dict) and row.get("concept_id") == "baseline_energy_plan":
            row["status"] = "READY" if baseline_ready else "INCOMPLETE"
            if baseline_ready:
                row.pop("reason", None)
            else:
                row["reason"] = "baseline_forecast_or_home_demand_incomplete"

    all_rows = logical + systems + planning + intelligence
    node_ids = {
        str(row.get("asset_id"))
        for row in all_rows
        if isinstance(row, dict) and row.get("asset_id")
    }
    layered["layer_health"] = {
        "logical": _health(logical),
        "system": _health(systems),
        "planning": _health(planning),
        "intelligence": _health(intelligence),
    }
    layered["materialization_records"] = [
        {
            "asset_id": row.get("asset_id"),
            "concept_id": row.get("concept_id"),
            "layer": row.get("layer"),
            "status": row.get("status"),
            "source_asset_ids": row.get("source_asset_ids") or [],
        }
        for row in all_rows
        if isinstance(row, dict)
    ]
    layered["dependency_diagnostics"] = {
        "node_count": len(node_ids),
        "edge_count": len(dependencies),
        "missing_source_nodes": sorted(
            {
                str(edge.get("from"))
                for edge in dependencies
                if edge.get("from") and str(edge.get("from")) not in node_ids
            }
        ),
        "missing_target_nodes": sorted(
            {
                str(edge.get("to"))
                for edge in dependencies
                if edge.get("to") and str(edge.get("to")) not in node_ids
            }
        ),
    }
    basis = {
        "logical": logical,
        "system": systems,
        "planning": planning,
        "intelligence": intelligence,
        "dependencies": dependencies,
    }
    layered["model_fingerprint"] = hashlib.sha256(
        json.dumps(
            basis, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()[:24]
    return layered
