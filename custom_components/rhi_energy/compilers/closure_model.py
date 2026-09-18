"""E0.14 layered closure metadata for the active Energy generation."""
from __future__ import annotations
from typing import Any


def _node(asset_id: str, concept_id: str, layer: str, status: str = "READY", reason: str | None = None):
    row = {"asset_id": asset_id, "concept_id": concept_id, "layer": layer, "owner": "rhi_energy", "status": status}
    if reason:
        row["reason"] = reason
    return row


def close_layered_energy_model(layered: dict[str, Any]) -> dict[str, Any]:
    """Add closure concepts without manufacturing readiness.

    Closure may add topology/dependency metadata, but it may not promote a concept to
    READY merely because a node exists. Runtime/public projections remain downstream
    of canonical dependency truth.
    """
    systems = list(layered.get("system_assets") or [])
    planning = list(layered.get("planning_assets") or [])
    intelligence = list(layered.get("intelligence_assets") or [])
    deps = list(layered.get("dependencies") or [])

    system_ids = {str(x.get("concept_id")): str(x.get("asset_id")) for x in systems if isinstance(x, dict)}
    balance = next((x for x in systems if isinstance(x, dict) and x.get("concept_id") == "site_energy_balance"), None)
    if "grid_system" not in system_ids:
        balance_ready = bool(balance and balance.get("status") == "READY")
        systems.append(
            _node(
                "grid_system:home",
                "grid_system",
                "system",
                "READY" if balance_ready else "INCOMPLETE",
                None if balance_ready else "site_energy_balance_incomplete",
            )
        )

    for concept, aid in (
        ("baseline_energy_plan", "baseline_plan:home"),
        ("flexible_load_plan", "flexible_plan:home"),
    ):
        if not any(x.get("concept_id") == concept for x in planning if isinstance(x, dict)):
            planning.append(
                _node(
                    aid,
                    concept,
                    "planning",
                    "INCOMPLETE",
                    "planning_dependencies_not_evaluated",
                )
            )

    if not any(x.get("concept_id") == "energy_retrospective" for x in intelligence if isinstance(x, dict)):
        intelligence.append(_node("retrospective:home", "energy_retrospective", "intelligence", "INCOMPLETE", "period_evidence_incomplete"))

    def add_edge(source: str, target: str, kind: str, criticality: str = "REQUIRED"):
        key = (source, target, kind)
        if not any((x.get("from"), x.get("to"), x.get("dependency_type")) == key for x in deps if isinstance(x, dict)):
            deps.append({"from": source, "to": target, "dependency_type": kind, "criticality": criticality})

    add_edge("home_consumption:home", "energy_outlook:home", "outlook_input")
    add_edge("metering_system:home", "retrospective:home", "retrospective_input")
    add_edge("operational_plan:home", "retrospective:home", "retrospective_input")
    add_edge("value_accounting_system:home", "retrospective:home", "retrospective_input", "QUALITY_ENHANCING")
    add_edge("flexible_plan:home", "allocation_set:operational", "allocation_input", "QUALITY_ENHANCING")

    def health(rows):
        states = {str(x.get("status") or "INCOMPLETE") for x in rows if isinstance(x, dict)}
        if states and states == {"READY"}:
            return "OK"
        if "READY" in states:
            return "DEGRADED"
        return "INCOMPLETE"

    all_rows = list(layered.get("logical_layer") or []) + systems + planning + intelligence
    layered.update({
        "layer_contract_version": "1.1.0",
        "system_assets": systems,
        "planning_assets": planning,
        "intelligence_assets": intelligence,
        "dependencies": deps,
        "materialization_records": [
            {"asset_id": x.get("asset_id"), "concept_id": x.get("concept_id"), "layer": x.get("layer"), "status": x.get("status"), "source_asset_ids": x.get("source_asset_ids") or []}
            for x in all_rows if isinstance(x, dict)
        ],
        "layer_health": {
            "logical": health(list(layered.get("logical_layer") or [])),
            "system": health(systems),
            "planning": health(planning),
            "intelligence": health(intelligence),
        },
    })
    layered.setdefault("runtime_rules", {}).update({
        "runtime_updates_values_only": True,
        "public_projection_reads_active_generation_only": True,
    })
    return layered
