"""Canonical Energy Public V2 product contract."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

try:
    from .const import RELEASE
    from .profile_catalog import EnergyProfileCatalogProvider, profile_context
    from .visual_catalog import resolve_visual_ref
    from .runtime.canonical_semantics import prop, pricing_properties, strategy_properties
    from .runtime.value_accounting import interval_actuals
    from .runtime.coverage import canonical_coverage
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy

    _root = _Path(__file__).resolve().parent
    RELEASE = _runpy.run_path(str(_root / "const.py"))["RELEASE"]
    _profiles = _runpy.run_path(str(_root / "profile_catalog.py"))
    _visual = _runpy.run_path(str(_root / "visual_catalog.py"))
    EnergyProfileCatalogProvider = _profiles["EnergyProfileCatalogProvider"]
    profile_context = _profiles["profile_context"]
    resolve_visual_ref = _visual["resolve_visual_ref"]
    _canonical = _runpy.run_path(str(_root / "runtime" / "canonical_semantics.py"))
    prop = _canonical["prop"]
    pricing_properties = _canonical["pricing_properties"]
    strategy_properties = _canonical["strategy_properties"]
    _value = _runpy.run_path(str(_root / "runtime" / "value_accounting.py"))
    interval_actuals = _value["interval_actuals"]
    _coverage = _runpy.run_path(str(_root / "runtime" / "coverage.py"))
    canonical_coverage = _coverage["canonical_coverage"]

PUBLIC_CONTRACT_V2 = "2.0.0"

PUBLIC_PROFILE_CONTRACT = "ENERGY_PROFILE_CATALOG_V2"


def _publication(asset: dict[str, Any]) -> dict[str, Any]:
    props = [row for row in asset.get("properties") or [] if isinstance(row, dict)]
    published = sorted({str(row.get("property_key")) for row in props if row.get("property_key")})
    required = sorted({
        str(row.get("property_key"))
        for row in props
        if row.get("property_key") and row.get("required") is True
    })
    resolved = sorted({
        str(row.get("property_key"))
        for row in props
        if row.get("property_key") and (row.get("resolution") or {}).get("status") == "RESOLVED"
    })
    missing_required = sorted(set(required) - set(published))
    unresolved_required = sorted(set(required) - set(resolved))
    return {
        "authority": "RHI_ENERGY_PUBLIC_CONTRACT_V2",
        "expected_property_keys": published,
        "published_property_keys": published,
        "required_property_keys": required,
        "missing_required_property_keys": missing_required,
        "resolved_property_keys": resolved,
        "unresolved_required_property_keys": unresolved_required,
        "complete": not missing_required,
        "resolution_complete": not unresolved_required,
    }


_PUBLIC_OPERATION_STATES = {"IDLE", "PENDING", "CONFIRMED", "REJECTED", "TIMED_OUT"}


def _public_operation(operation: dict[str, Any] | None) -> dict[str, Any]:
    """Return the single public lifecycle shape for writes and commands."""
    row = deepcopy(operation or {})
    raw_status = str(row.get("status") or row.get("execution_status") or "IDLE").upper()
    aliases = {
        "SUCCESS": "CONFIRMED",
        "COMPLETED": "CONFIRMED",
        "FAILED": "REJECTED",
        "ERROR": "REJECTED",
        "TIMEOUT": "TIMED_OUT",
    }
    status = aliases.get(raw_status, raw_status)
    if status not in _PUBLIC_OPERATION_STATES:
        status = "IDLE"
    return {
        "operation_id": row.get("operation_id"),
        "status": status,
        "reason": row.get("reason") or row.get("error"),
        "requested_at": row.get("requested_at"),
        "completed_at": row.get("completed_at"),
        "requested_value": deepcopy(row.get("requested_value")),
        "readback_value": deepcopy(row.get("readback_value")),
    }


def _property_presentation_family(property_key: str, row: dict[str, Any]) -> str:
    """Classify canonical properties once in the backend for consistent UX grouping."""
    key = str(property_key or "").strip().lower()
    if row.get("control_capability") is True or row.get("write_supported") is True:
        return "control"
    if any(token in key for token in ("power", "energy", "soc", "capacity", "current_a", "voltage", "flow")):
        return "energy"
    if any(token in key for token in ("target", "reserve", "policy", "mode", "deadline", "ready_by", "limit", "profile")):
        return "configuration"
    if any(token in key for token in ("source", "connection", "integration", "device", "availability", "health")):
        return "source_connectivity"
    if any(token in key for token in ("reason", "diagnostic", "revision", "binding", "provenance")):
        return "diagnostics"
    return "summary"


def _property_presentation_role(property_key: str, row: dict[str, Any], asset_type: str) -> str:
    """Publish the intended product depth so UX does not have to guess."""
    key = str(property_key or "").strip().lower()
    family = _property_presentation_family(key, row)
    if row.get("control_capability") is True or row.get("write_supported") is True:
        return "configuration"
    if family == "diagnostics" or any(
        token in key
        for token in ("source_", "binding", "provenance", "revision", "raw_", "integration", "health_reason")
    ):
        return "diagnostics"
    primary_tokens = (
        "power_kw", "energy_today", "soc_pct", "available_kwh", "flow_direction",
        "operating_state", "state", "status", "energy_to_target", "required_energy",
        "ready_by", "deadline", "net_power",
    )
    if any(token in key for token in primary_tokens):
        return "key"
    if asset_type in {"battery", "battery_system"} and any(token in key for token in ("capacity_kwh", "reserve_soc")):
        return "key"
    return "detail"


def _decorate_objects(
    objects: list[dict[str, Any]],
    property_operations: dict[str, dict[str, Any]] | None = None,
    appearance_preferences: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    operation_rows = property_operations or {}
    appearance_rows = appearance_preferences or {}
    for raw in objects:
        if not isinstance(raw, dict) or raw.get("product_projection") is False:
            continue
        asset = deepcopy(raw)
        asset_type = str(asset.get("asset_type") or asset.get("object_class") or "").strip()
        if asset_type:
            asset["asset_type"] = asset_type
        context = profile_context(asset)
        if not asset.get("profile_id"):
            asset["profile_id"] = context.get("profile_id")
        if not asset.get("technical_specification"):
            asset["technical_specification"] = context.get("technical_specification") or {}
        asset["capabilities"] = sorted(
            set(asset.get("capabilities") or [])
            | set(context.get("profile_capabilities") or [])
        )
        source_visual_ref = resolve_visual_ref(
            asset_type,
            asset.get("visual_ref"),
            context.get("profile_visual_ref"),
        )
        asset_id = str(asset.get("asset_id") or "")
        source_domain = str(asset.get("source_domain") or "").strip().lower()
        producer_owned = (
            source_domain == "mobility"
            or asset_type in {"vehicle", "charger", "flexible_load"}
            or str(source_visual_ref or "").startswith("mobility.")
        )
        configured_visual_ref = str(
            ((appearance_rows.get(asset_id) or {}).get("visual_ref")) or ""
        ).strip()
        valid_configured_visual_ref = (
            configured_visual_ref
            if (
                not producer_owned
                and configured_visual_ref.startswith(f"energy.logical.{asset_type}.")
            )
            else ""
        )
        asset["visual_ref"] = valid_configured_visual_ref or source_visual_ref
        appearance_property_id = f"appearance:{asset_id}:visual_ref"
        appearance_operation = _public_operation(operation_rows.get(appearance_property_id))
        asset["appearance"] = {
            "owner_domain": "rhi_energy",
            "editable": not producer_owned,
            "configured_visual_ref": valid_configured_visual_ref or None,
            "effective_visual_ref": asset["visual_ref"],
            "profile_visual_ref": context.get("profile_visual_ref"),
            "source_visual_ref": source_visual_ref,
            "write": (
                {
                    "supported": True,
                    "operation_id": "energy.property.write",
                    "service": "rhi_energy.write_property",
                    "data": {"property_id": appearance_property_id},
                    "value_parameter": "value",
                    "readback_property": appearance_property_id,
                }
                if not producer_owned and asset_id
                else {"supported": False}
            ),
            "operation": appearance_operation,
        }
        asset["property_publication"] = _publication(asset)
        provenance_rows: list[dict[str, Any]] = []
        for property_row in asset.get("properties") or []:
            property_key = str(property_row.get("property_key") or "")
            family = _property_presentation_family(property_key, property_row)
            role = _property_presentation_role(property_key, property_row, asset_type)
            property_row["presentation"] = {
                "family": family,
                "role": role,
                "surface": {
                    "key": "key_properties",
                    "configuration": "configuration",
                    "detail": "details",
                    "diagnostics": "diagnostics",
                }[role],
                "primary": role == "key",
                "technical": role == "diagnostics",
            }
            resolution = property_row.get("resolution") or {}
            for evidence in resolution.get("provenance") or []:
                if isinstance(evidence, dict) and evidence not in provenance_rows:
                    provenance_rows.append(deepcopy(evidence))
        asset["provenance"] = provenance_rows
        asset["source_refs"] = sorted({
            str(value)
            for row in provenance_rows
            for value in (row.get("binding_id"), row.get("current_entity_id"))
            if value
        })
        controls = []
        for prop in asset.get("properties") or []:
            property_key = str(prop.get("property_key") or "")
            write_supported = prop.get("write_supported") is True
            if write_supported and property_key:
                prop["editable"] = True
                prop["write"] = {
                    "operation_id": "energy.property.write",
                    "service": "rhi_energy.write_property",
                    "data": {"property_id": f"logical:{asset.get('asset_id')}:{property_key}"},
                    "value_parameter": "value",
                    "readback_property": property_key,
                }
                operation = deepcopy(
                    operation_rows.get(
                        f"logical:{asset.get('asset_id')}:{property_key}"
                    ) or {}
                )
                public_operation = _public_operation(operation)
                prop["operation_state"] = public_operation["status"]
                prop["operation"] = public_operation
            if prop.get("control_capability") is not True:
                continue
            control = {
                "control_id": property_key,
                "target_asset_id": asset.get("asset_id"),
                "kind": "action" if str(prop.get("kind") or "") == "action" else "property_write",
                "editor": prop.get("editor"),
                "supported": write_supported,
                "readback_required": True,
                "reason": (
                    "authoritative_state_readback_available"
                    if write_supported
                    else str(prop.get("control_reason") or "authoritative_readback_not_defined")
                ),
            }
            if write_supported:
                control["operation_id"] = "energy.property.write"
                control["property_id"] = f"logical:{asset.get('asset_id')}:{property_key}"
                control["readback_property"] = property_key
                if prop.get("constraints"):
                    control["constraints"] = deepcopy(prop["constraints"])
            controls.append(control)
        asset["controls"] = controls
        decorated.append(asset)
    return decorated


def _profile_catalog() -> list[dict[str, Any]]:
    """Return the same read-only local product-profile pattern used by Mobility."""
    return EnergyProfileCatalogProvider().snapshot()["profiles"]


def _core_status(required: dict[str, Any], *, unavailable_reason: str) -> dict[str, Any]:
    """Return fail-closed product status for one core Energy block."""
    missing = [key for key, value in required.items() if value is None]
    if not missing:
        return {"status": "AVAILABLE", "reason": None, "missing_fields": []}
    return {
        "status": "UNAVAILABLE",
        "reason": unavailable_reason,
        "missing_fields": missing,
    }


def _semantic_field(value: Any, *, unit: str | None = None, reason: str) -> dict[str, Any]:
    """Publish one canonical scalar without coercing missing evidence to zero."""
    available = value is not None
    return {
        "value": deepcopy(value),
        "unit": unit,
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "quality": "CANONICAL" if available else "UNKNOWN",
        "reason": None if available else reason,
    }


def _planning_projection(plan: dict[str, Any]) -> dict[str, Any]:
    """Expose canonical D0/D1 planning without discarding Tactical detail.

    The planner is the semantic authority. Public V2 adds stable summary fields but
    must preserve its buckets, lanes, demand/supply/balance, candidates and quality
    so UX consumers never need to reconstruct the plan.
    """
    horizons: dict[str, Any] = {}
    for horizon_id in ("D0", "D1"):
        raw = deepcopy(((plan.get("planning_horizons") or {}).get(horizon_id) or {}))
        demand = raw.get("demand") or {}
        quality = raw.get("quality") or {}
        home = demand.get("home_kwh")
        flexible_required = demand.get("flexible_known_need_kwh")
        flexible_planned = demand.get("flexible_scheduled_kwh")
        flexible_still = demand.get("flexible_deferred_kwh")
        required = (
            round(float(home) + float(flexible_required), 4)
            if home is not None and flexible_required is not None
            else None
        )
        planned = (
            round(float(home) + float(flexible_planned), 4)
            if home is not None and flexible_planned is not None
            else None
        )
        still = flexible_still if required is not None and planned is not None else None
        canonical_available = quality.get("availability") == "AVAILABLE"
        usable = all(value is not None for value in (
            required, planned, still, flexible_required, flexible_planned, flexible_still
        ))
        status = "AVAILABLE" if canonical_available and usable else "UNAVAILABLE"
        reason = None if status == "AVAILABLE" else (
            "planning_outcome_incomplete" if raw else "planning_horizon_missing"
        )
        publish_totals = status == "AVAILABLE"
        horizons[horizon_id] = {
            **raw,
            "horizon_id": str(raw.get("horizon_id") or horizon_id),
            "required_kwh": required if publish_totals else None,
            "planned_kwh": planned if publish_totals else None,
            "executed_kwh": None,
            "still_to_plan_kwh": still if publish_totals else None,
            "flexible_required_kwh": flexible_required if publish_totals else None,
            "flexible_planned_kwh": flexible_planned if publish_totals else None,
            "flexible_executed_kwh": None,
            "flexible_still_to_plan_kwh": flexible_still if publish_totals else None,
            "partial_totals": {
                "required_kwh": required,
                "planned_kwh": planned,
                "still_to_plan_kwh": still,
                "flexible_required_kwh": flexible_required,
                "flexible_planned_kwh": flexible_planned,
                "flexible_still_to_plan_kwh": flexible_still,
            },
            "status": status,
            "reason": reason,
            "execution_status": "NOT_MEASURED",
            "execution_reason": "advisory_plan_has_no_authoritative_execution_meter",
            "quality": deepcopy(quality),
            "source_refs": deepcopy(raw.get("source_refs") or []),
            "buckets": deepcopy(raw.get("buckets") or []),
        }
    flexible_plan = deepcopy(plan.get("flexible_plan") or {})
    assets = [
        deepcopy(row)
        for row in flexible_plan.get("assets") or []
        if isinstance(row, dict) and row.get("asset_id")
    ]
    for row in assets:
        eligible = row.get("planning_eligible") is True
        blockers = list(row.get("missing_inputs") or row.get("blockers") or [])
        if not eligible and not blockers:
            blockers = ["planning_input_incomplete"]
        row["missing_inputs"] = [] if eligible else blockers
        row["reason"] = None if eligible else str(row.get("reason") or blockers[0])
        row["D0"] = {
            "planned_kwh": row.get("planned_today_kwh") if eligible else None,
            "still_after_horizon_kwh": row.get("still_after_today_kwh") if eligible else None,
        }
        row["D1"] = {
            "planned_kwh": row.get("planned_tomorrow_kwh") if eligible else None,
            "still_after_horizon_kwh": row.get("still_to_plan_kwh") if eligible else None,
        }
    return {
        "plan_id": plan.get("plan_id"),
        "generated_at": plan.get("generated_at"),
        "health": plan.get("health") or "UNKNOWN",
        "reason": plan.get("reason"),
        "baseline_plan": deepcopy(plan.get("baseline_plan") or {}),
        "flexible_plan": flexible_plan,
        "assets": assets,
        "participant_count": len(assets),
        "eligible_participant_count": sum(row.get("planning_eligible") is True for row in assets),
        "incomplete_participant_count": sum(row.get("planning_eligible") is not True for row in assets),
        "totals_complete": flexible_plan.get("totals_complete") is True,
        "battery_ledger": deepcopy(plan.get("battery_ledger") or {}),
        "execution_policy": deepcopy(plan.get("execution_policy") or {}),
        "horizons": horizons,
    }

def _value_accounting_outcome(selected_period: str, selected_value: dict[str, Any]) -> dict[str, Any]:
    value = selected_value.get("net_financial_result_eur")
    if value is not None:
        return {
            "value": value,
            "unit": "EUR",
            "status": "AVAILABLE",
            "reason": None,
            "period_id": selected_period,
        }
    reason = "selected_period_value_evidence_incomplete"
    if not selected_value:
        reason = "selected_period_not_materialized"
    elif selected_value.get("actual_complete") is False:
        reason = "selected_period_actuals_incomplete"
    return {
        "value": None,
        "unit": "EUR",
        "status": "UNAVAILABLE",
        "reason": reason,
        "period_id": selected_period,
    }



def _metering_projection(metering_state: dict[str, Any], selected_period: str) -> dict[str, Any]:
    """Publish canonical period measurements without inferring remediation from command availability."""
    raw_periods = deepcopy((metering_state or {}).get("periods") or {})
    periods: dict[str, Any] = {}
    measured_key_map = {
        "solar_production_kwh": "solar_kwh",
        "grid_import_kwh": "grid_import_kwh",
        "grid_export_kwh": "grid_export_kwh",
        "site_consumption_kwh": "site_consumption_kwh",
        "home_consumption_kwh": "home_consumption_kwh",
        "battery_charge_kwh": "battery_charge_kwh",
        "battery_discharge_kwh": "battery_discharge_kwh",
        "flexible_loads_energy_in_kwh": "flexible_loads_energy_in_kwh",
    }
    for period_id in ("hour", "today", "week", "month", "year"):
        raw = deepcopy(raw_periods.get(period_id) or {})
        measured = {
            public_key: deepcopy(raw.get(store_key))
            for public_key, store_key in measured_key_map.items()
        }
        has_measurement = any(value is not None for value in measured.values())
        quality = str(raw.get("quality") or "UNKNOWN").upper()
        availability = "AVAILABLE" if has_measurement else "UNAVAILABLE"
        reset_required = raw.get("baseline_reset_required") is True
        periods[period_id] = {
            "period_id": period_id,
            "period_key": raw.get("period_key"),
            "availability": availability,
            "measurement_state": availability,
            "quality": quality,
            "baseline_reset_required": reset_required,
            "user_action_required": reset_required,
            "baseline_reset_at": raw.get("baseline_reset_at"),
            "gap_count": int(raw.get("gap_count") or 0),
            "field_quality": deepcopy(raw.get("field_quality") or {}),
            "field_coverage_seconds": deepcopy(raw.get("field_coverage_seconds") or {}),
            "financial_quality": deepcopy(raw.get("financial_quality") or {}),
            "summary": {
                "measured": measured,
                "quality": {
                    "period": quality,
                    "health": quality,
                    "measurement_state": availability,
                    "availability": availability,
                    "user_action_required": reset_required,
                },
            },
        }
    selected = periods.get(selected_period) or {
        "period_id": selected_period,
        "availability": "UNAVAILABLE",
        "measurement_state": "UNAVAILABLE",
        "quality": "UNKNOWN",
        "baseline_reset_required": False,
        "user_action_required": False,
        "summary": {"measured": {}, "quality": {"period": "UNKNOWN", "measurement_state": "UNAVAILABLE"}},
    }
    return {
        "selected_period_id": selected_period,
        "selected": deepcopy(selected),
        "periods": periods,
        "period_order": ["hour", "today", "week", "month", "year"],
        "remediation_semantics": "reset_required_is_evidence_owned_not_command_presence",
    }


def _retrospective_projection(
    planning: dict[str, Any],
    metering: dict[str, Any],
    command_state: dict[str, Any],
) -> dict[str, Any]:
    """Expose truthful retrospective evidence readiness; never synthesize a performance score."""
    horizons = (planning or {}).get("horizons") or {}
    planning_ready = any(
        str((horizons.get(horizon_id) or {}).get("status") or "").upper() == "AVAILABLE"
        for horizon_id in ("D0", "D1")
    )
    selected_metering = (metering or {}).get("selected") or {}
    measured_ready = str(selected_metering.get("availability") or "").upper() == "AVAILABLE"
    terminal = [
        deepcopy(row)
        for row in (command_state or {}).values()
        if isinstance(row, dict)
        and str(row.get("status") or "").upper() in {"CONFIRMED", "REJECTED", "TIMED_OUT"}
    ]
    execution_ready = bool(terminal)
    prerequisites = [
        {
            "prerequisite_id": "planning_outcome",
            "label": "Planning outcomes",
            "state": "READY" if planning_ready else "PENDING",
            "reason": None if planning_ready else "canonical_planning_outcome_not_available",
        },
        {
            "prerequisite_id": "execution_evidence",
            "label": "Execution results",
            "state": "READY" if execution_ready else "PENDING",
            "reason": None if execution_ready else "no_persisted_execution_result_available",
        },
        {
            "prerequisite_id": "completed_metering",
            "label": "Measured energy",
            "state": "READY" if measured_ready else "PENDING",
            "reason": None if measured_ready else "selected_metering_period_has_no_measurement_evidence",
        },
    ]
    ready_count = sum(row["state"] == "READY" for row in prerequisites)
    evidence_ready = ready_count == len(prerequisites)
    return {
        "contract_id": "RHI_ENERGY_RETROSPECTIVE_V2",
        "status": "NOT_EVALUATED" if evidence_ready else "COLLECTING_EVIDENCE",
        "reason": (
            "objective_performance_model_not_published"
            if evidence_ready
            else "retrospective_prerequisites_incomplete"
        ),
        "prerequisites": prerequisites,
        "evidence_coverage_pct": round(ready_count / len(prerequisites) * 100, 1),
        "confidence": "NOT_ASSESSED",
        "score": None,
        "trend": None,
        "objectives": [],
        "execution_kpis": {
            "result_count": len(terminal),
            "success_count": sum(str(row.get("status") or "").upper() == "CONFIRMED" for row in terminal),
            "failure_count": sum(str(row.get("status") or "").upper() in {"REJECTED", "TIMED_OUT"} for row in terminal),
            "pending_count": sum(str(row.get("status") or "").upper() == "PENDING" for row in (command_state or {}).values() if isinstance(row, dict)),
        },
        "score_semantics": "no_score_without_backend_owned_objectives_and_closed_evidence",
    }


def _build_core(source: dict[str, Any]) -> dict[str, Any]:
    """Project stable current-home Energy truth without re-deriving semantics.

    Every value comes from canonical runtime facts or canonical flexible assets.
    Optional object-detail health never controls these product-level statuses.
    """
    facts = source.get("facts") or {}
    flexible_assets = [
        deepcopy(row)
        for row in source.get("flexible_assets") or []
        if isinstance(row, dict)
        and str(row.get("participation_state") or "participating").strip().lower() != "infrastructure_only"
        and row.get("infrastructure_only") is not True
    ]
    battery = {
        "power_kw": facts.get("battery.power_kw"),
        "soc_pct": facts.get("battery.soc_pct"),
        "state": facts.get("battery.state"),
        "capacity_kwh": facts.get("battery.capacity_kwh"),
        "available_kwh": facts.get("battery.available_kwh"),
        "reserve_target_pct": facts.get("battery.reserve_target_pct"),
    }
    battery.update(_core_status(
        {"power_kw": battery["power_kw"], "soc_pct": battery["soc_pct"], "state": battery["state"]},
        unavailable_reason="battery_core_truth_incomplete",
    ))
    battery["fields"] = {
        "power_kw": _semantic_field(battery["power_kw"], unit="kW", reason="battery_power_unavailable"),
        "soc_pct": _semantic_field(battery["soc_pct"], unit="%", reason="battery_soc_unavailable"),
        "state": _semantic_field(battery["state"], reason="battery_state_unavailable"),
        "capacity_kwh": _semantic_field(battery["capacity_kwh"], unit="kWh", reason="battery_capacity_unavailable"),
        "available_kwh": _semantic_field(battery["available_kwh"], unit="kWh", reason="battery_available_energy_unavailable"),
        "reserve_target_pct": _semantic_field(battery["reserve_target_pct"], unit="%", reason="battery_reserve_unavailable"),
    }
    battery["contributors"] = [
        {
            "asset_id": row.get("asset_id"),
            "display_name": row.get("display_name"),
            "integration_domain": row.get("integration_domain"),
            "power_kw": row.get("power_kw"),
            "soc_pct": row.get("soc_pct"),
            "capacity_kwh": row.get("capacity_kwh"),
            "available_kwh": row.get("available_kwh"),
            "state": row.get("status"),
            "health": row.get("health"),
            "availability": (
                "AVAILABLE"
                if any(
                    row.get(key) is not None
                    for key in ("power_kw", "soc_pct", "capacity_kwh", "available_kwh", "status")
                )
                else "UNAVAILABLE"
            ),
        }
        for row in source.get("battery_units") or []
        if isinstance(row, dict)
    ]

    solar = {"power_kw": facts.get("solar.power_kw")}
    solar.update(_core_status(
        {"power_kw": solar["power_kw"]},
        unavailable_reason="solar_core_truth_incomplete",
    ))
    solar["fields"] = {
        "power_kw": _semantic_field(solar["power_kw"], unit="kW", reason="solar_power_unavailable"),
    }

    grid = {
        "net_power_kw": facts.get("grid.net_power_kw"),
        "import_power_kw": facts.get("grid_import.power_kw"),
        "export_power_kw": facts.get("grid_export.power_kw"),
        "flow_direction": facts.get("grid.flow_direction"),
    }
    grid.update(_core_status(
        {
            "net_power_kw": grid["net_power_kw"],
            "import_power_kw": grid["import_power_kw"],
            "export_power_kw": grid["export_power_kw"],
            "flow_direction": grid["flow_direction"],
        },
        unavailable_reason=(
            "grid_direction_unresolved"
            if grid["flow_direction"] is None
            else "grid_core_truth_incomplete"
        ),
    ))
    grid["fields"] = {
        "net_power_kw": _semantic_field(grid["net_power_kw"], unit="kW", reason="grid_net_power_unavailable"),
        "import_power_kw": _semantic_field(grid["import_power_kw"], unit="kW", reason="grid_import_power_unavailable"),
        "export_power_kw": _semantic_field(grid["export_power_kw"], unit="kW", reason="grid_export_power_unavailable"),
        "flow_direction": _semantic_field(grid["flow_direction"], reason="grid_direction_unresolved"),
    }

    consumption = {"power_kw": facts.get("site_consumption.power_kw")}
    consumption.update(_core_status(
        {"power_kw": consumption["power_kw"]},
        unavailable_reason="site_consumption_core_truth_incomplete",
    ))
    consumption["fields"] = {
        "power_kw": _semantic_field(consumption["power_kw"], unit="kW", reason="site_consumption_unavailable"),
    }

    home = {"power_kw": facts.get("home_consumption.power_kw")}
    home.update(_core_status(
        {"power_kw": home["power_kw"]},
        unavailable_reason="home_consumption_core_truth_incomplete",
    ))
    home["fields"] = {
        "power_kw": _semantic_field(home["power_kw"], unit="kW", reason="home_consumption_unavailable"),
    }

    producer_available = bool(
        (source.get("producer_publication_availability") or {}).get("mobility")
    )
    flexible = {
        "power_kw": facts.get("flexible_loads.power_kw"),
        "attributed_power_kw": facts.get("flexible_loads.attributed_power_kw"),
        "asset_count": len(flexible_assets),
        "assets": flexible_assets,
        "producer_available": producer_available,
    }
    flexible_required = {
        "power_kw": flexible["power_kw"],
        "attributed_power_kw": flexible["attributed_power_kw"],
        "producer_available": True if producer_available else None,
    }
    flexible.update(_core_status(
        flexible_required,
        unavailable_reason=(
            "mobility_flexible_load_publication_unavailable"
            if not producer_available
            else "flexible_load_core_truth_incomplete"
        ),
    ))
    flexible["fields"] = {
        "power_kw": _semantic_field(flexible["power_kw"], unit="kW", reason="flexible_load_power_unavailable"),
        "attributed_power_kw": _semantic_field(flexible["attributed_power_kw"], unit="kW", reason="flexible_load_attribution_unavailable"),
    }

    return {
        "contract_id": "RHI_ENERGY_CORE_V2",
        "battery": battery,
        "solar": solar,
        "grid": grid,
        "consumption": consumption,
        "home": home,
        "flexible": flexible,
    }


def _relationships(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for asset in snapshot.get("logical_assets") or []:
        if not isinstance(asset, dict) or asset.get("product_projection") is False:
            continue
        source = str(asset.get("parent_asset_id") or "")
        target = str(asset.get("asset_id") or "")
        if source and target:
            relationship_id = f"energy:{source}:contains:{target}"
            rows[relationship_id] = {
                "relationship_id": relationship_id,
                "source_asset_id": source,
                "target_asset_id": target,
                "relationship_type": "contains",
                "source_domain": "energy",
            }
    logical_assets = [
        item for item in snapshot.get("logical_assets") or []
        if isinstance(item, dict) and item.get("product_projection") is not False
    ]
    home_asset = next((item for item in logical_assets if item.get("object_class") == "home_consumption"), None)
    home_id = str((home_asset or {}).get("asset_id") or "home_consumption")
    for asset in logical_assets:
        aid = str(asset.get("asset_id") or "")
        object_class = str(asset.get("object_class") or "")
        if not aid:
            continue
        relation_type = None
        source, target = aid, home_id
        flow_role = None
        if object_class == "solar_inverter":
            relation_type, flow_role = "supplies", "solar_supply"
        elif object_class == "battery":
            relation_type, flow_role = "exchanges_with", "stationary_battery"
        elif object_class == "grid_connection":
            relation_type, flow_role = "exchanges_with", "grid_boundary"
        elif object_class == "flexible_load":
            relation_type, flow_role = "supplies", "flexible_demand"
            source, target = home_id, aid
        if relation_type:
            relationship_id = f"energy:physical:{source}:{relation_type}:{target}"
            rows[relationship_id] = {
                "relationship_id": relationship_id,
                "source_asset_id": source,
                "target_asset_id": target,
                "relationship_type": relation_type,
                "source_domain": "energy",
                "physical": True,
                "flow_role": flow_role,
            }
    for index, relation in enumerate(snapshot.get("connections") or []):
        if not isinstance(relation, dict):
            continue
        # Producer-owned Mobility connection rows use asset_id for the physical
        # charger and connected_asset_id for the assigned vehicle/load. Preserve
        # those canonical identities instead of requiring a pre-shaped graph edge.
        source = (
            relation.get("source_asset_id")
            or relation.get("from_asset_id")
            or relation.get("source")
            or relation.get("asset_id")
        )
        target = (
            relation.get("target_asset_id")
            or relation.get("to_asset_id")
            or relation.get("target")
            or relation.get("connected_asset_id")
            or relation.get("connected_consumer_id")
        )
        if not source or not target:
            continue
        relationship_id = str(relation.get("relationship_id") or f"external:{index}:{source}:{target}")
        rows[relationship_id] = {
            **deepcopy(relation),
            "relationship_id": relationship_id,
            "source_asset_id": str(source),
            "target_asset_id": str(target),
            "relationship_type": str(relation.get("relationship_type") or relation.get("type") or "connected_to"),
            "source_domain": str(relation.get("source_domain") or "external"),
        }
    return [rows[key] for key in sorted(rows)]


def _apply_configuration_operation_state(
    rows: list[dict[str, Any]],
    property_operations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out = deepcopy(rows)
    for row in out:
        property_id = str(row.get("property_id") or row.get("key") or "")
        if not property_id or row.get("editable") is not True:
            continue
        operation = deepcopy(property_operations.get(property_id) or {})
        public_operation = _public_operation(operation)
        row["operation_state"] = public_operation["status"]
        row["write_state"] = public_operation["status"]
        row["write_status"] = public_operation["status"]
        row["readback_value"] = deepcopy(public_operation.get("readback_value"))
        row["operation"] = public_operation
    return out


def _strategy_profile_projection(
    configured_rows: list[dict[str, Any]],
    effective_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Publish domain-owned Settings topics; UX renders them but never invents grouping."""
    topics = {
        "home": ("home_priorities", "Home & priorities", 10),
        "battery": ("battery", "Battery", 20),
        "flexible_loads": ("ev_charging", "EV charging", 30),
        "solar": ("solar", "Solar", 40),
        "grid": ("grid_tariffs", "Grid & tariffs", 50),
        "resilience": ("home_resilience", "Home & resilience", 60),
    }
    effective_by_group: dict[str, list[dict[str, Any]]] = {}
    for row in effective_rows:
        group = str(row.get("group") or row.get("asset_id") or "home")
        effective_by_group.setdefault(group, []).append(deepcopy(row))
    groups: dict[str, dict[str, Any]] = {}
    for row in configured_rows:
        group = str(row.get("group") or row.get("asset_id") or "home")
        topic_id, topic_label, display_order = topics.get(
            group,
            (group, group.replace("_", " ").title(), 90),
        )
        profile = groups.setdefault(group, {
            "profile_id": group,
            "topic_id": topic_id,
            "topic_label": topic_label,
            "display_order": display_order,
            "display_name": topic_label,
            "description": f"Adjust {topic_label.lower()} settings.",
            "configured_properties": [],
            "effective_properties": deepcopy(effective_by_group.get(group) or []),
        })
        profile["configured_properties"].append(deepcopy(row))
    return [
        groups[key]
        for key in ("home", "battery", "flexible_loads", "solar", "grid", "resilience")
        if key in groups
    ]


def _strategy_behavior_projection(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Publish read-only longer-term behavior topics from effective Settings truth."""
    out: list[dict[str, Any]] = []
    for profile in profiles:
        effective = [
            deepcopy(row)
            for row in profile.get("effective_properties") or []
            if isinstance(row, dict)
        ]
        if not effective:
            continue
        out.append({
            "topic_id": profile.get("topic_id"),
            "topic_label": profile.get("topic_label") or profile.get("display_name"),
            "display_order": profile.get("display_order"),
            "source_profile_id": profile.get("profile_id"),
            "properties": effective,
            "read_only": True,
            "semantics": "effective_settings_interpretation",
        })
    return out


def _settings_participation_projection(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Project canonical control/planning relationships without frontend inference."""
    logical = [row for row in source.get("logical_assets") or [] if isinstance(row, dict)]
    by_id = {str(row.get("asset_id")): row for row in logical if row.get("asset_id")}
    roots: list[dict[str, Any]] = []

    battery_systems = [
        row for row in logical if str(row.get("object_class") or "") == "battery_system"
    ]
    batteries = [row for row in logical if str(row.get("object_class") or "") == "battery"]
    for system in battery_systems:
        sid = str(system.get("asset_id") or "")
        children = [
            {
                "asset_id": str(row.get("asset_id")),
                "display_name": row.get("display_name"),
                "asset_type": "battery",
                "relationship_type": "contains",
            }
            for row in batteries
            if str(row.get("parent_asset_id") or "") == sid
        ]
        roots.append({
            "asset_id": sid,
            "display_name": system.get("display_name") or "Home Battery",
            "asset_type": "battery_system",
            "participation_role": "storage",
            "children": children,
        })

    flexible_by_id = {
        str(row.get("asset_id")): row
        for row in source.get("flexible_assets") or []
        if isinstance(row, dict) and row.get("asset_id")
    }
    for connection in source.get("connections") or []:
        if not isinstance(connection, dict):
            continue
        charger_id = str(connection.get("asset_id") or connection.get("source_asset_id") or "")
        if not charger_id:
            continue
        child_id = str(
            connection.get("connected_asset_id")
            or connection.get("connected_consumer_id")
            or connection.get("target_asset_id")
            or ""
        )
        child = flexible_by_id.get(child_id) or by_id.get(child_id) or {}
        display_name = (
            connection.get("display_name")
            or connection.get("charger_display_name")
            or connection.get("physical_connection_display_name")
            or connection.get("effective_connection_display_name")
            or charger_id
        )
        roots.append({
            "asset_id": charger_id,
            "display_name": display_name,
            "asset_type": "charger",
            "participation_role": "flexible_connection",
            "connection_state": connection.get("connection_state") or connection.get("state"),
            "children": (
                [{
                    "asset_id": child_id,
                    "display_name": child.get("display_name") or connection.get("connected_asset_display_name") or child_id,
                    "asset_type": str(child.get("asset_type") or child.get("ux_asset_type") or "vehicle"),
                    "relationship_type": str(connection.get("relationship_type") or "connected_to"),
                    "planning_eligible": child.get("planning_eligible"),
                    "planning_input_ready": child.get("planning_input_ready"),
                }]
                if child_id else []
            ),
        })
    return roots


def _decorate_commands(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = deepcopy(raw)
        lifecycle_source = {
            **row,
            "requested_value": deepcopy(row.get("requested_value") if "requested_value" in row else (row.get("parameters") or {})),
            "readback_value": deepcopy(row.get("readback_value") if "readback_value" in row else (row.get("readback") or {})),
        }
        public_operation = _public_operation(lifecycle_source)
        row["operation_state"] = public_operation["status"]
        row["operation"] = public_operation
        out.append(row)
    return out


def _battery_reserve_write_supported(concepts: dict[str, Any]) -> bool:
    """Return physical Battery reserve-control support across accepted providers."""
    providers = (concepts.get("battery_system") or {}).get("providers") or []
    return any(
        bool(provider.get("reserve_binding") or provider.get("reserve_bindings"))
        for provider in providers
        if isinstance(provider, dict)
    )


def build_public_contract_v2(
    snapshot: dict[str, Any],
    store_data: dict[str, Any],
    command_rows: list[dict[str, Any]],
    model: dict[str, Any],
) -> dict[str, Any]:
    """Build the single authoritative object-centric product contract from canonical runtime truth."""
    source = deepcopy(snapshot)
    source["settings"] = deepcopy(store_data.get("settings") or {})
    concepts = model.get("concepts") or {}
    source["battery_reserve_write_supported"] = _battery_reserve_write_supported(concepts)
    property_operations = deepcopy(store_data.get("property_operation_state") or {})
    settings = deepcopy(store_data.get("settings") or {})
    objects = _decorate_objects(
        deepcopy(source.get("logical_assets") or []),
        property_operations,
        deepcopy(settings.get("appearance") or {}),
    )
    pricing_rows = _apply_configuration_operation_state(
        pricing_properties(source.get("facts") or {}, settings),
        property_operations,
    )
    strategy_rows = _apply_configuration_operation_state(
        strategy_properties(settings),
        property_operations,
    )
    pricing_by_id = {
        str(row.get("property_id") or row.get("key") or ""): row
        for row in pricing_rows
        if isinstance(row, dict)
    }
    tariff_ids = (
        "pricing.import_network_eur_kwh",
        "pricing.import_levies_eur_kwh",
        "pricing.import_vat_pct",
    )
    configured_tariff_ids = [
        key for key in tariff_ids
        if (pricing_by_id.get(key) or {}).get("value") is not None
    ]
    if len(configured_tariff_ids) == 0:
        pricing_accounting_mode = "MARKET_ONLY"
        tariff_blockers: list[str] = []
    elif len(configured_tariff_ids) == len(tariff_ids):
        pricing_accounting_mode = "FULL_TARIFF"
        tariff_blockers = []
    else:
        pricing_accounting_mode = "PARTIAL_TARIFF_CONFIGURATION"
        tariff_blockers = [key for key in tariff_ids if key not in configured_tariff_ids]
    market_blockers = (
        ["pricing.spot_eur_kwh"]
        if (pricing_by_id.get("pricing.import_price_current_eur_kwh") or {}).get("value") is None
        else []
    )
    pricing_blockers = market_blockers + tariff_blockers
    metering_rows = _apply_configuration_operation_state(
        [
            prop(
                "metering",
                "metering.selected_period",
                str(settings.get("metering_selected_period") or "today"),
                editable=True,
                editor="select",
                operation_id="energy.metering.set_property",
                constraints={"allowed": ["hour", "today", "week", "month", "year"]},
                choices=[
                    {"value": "hour", "label": "This hour"},
                    {"value": "today", "label": "Today"},
                    {"value": "week", "label": "This week"},
                    {"value": "month", "label": "This month"},
                    {"value": "year", "label": "This year"},
                ],
                group="metering",
            )
        ],
        property_operations,
    )
    canonical_configuration = {
        "pricing": {
            "properties": pricing_rows,
            "availability": "AVAILABLE" if any(row.get("availability") == "AVAILABLE" for row in pricing_rows) else "UNAVAILABLE",
            "accounting_mode": pricing_accounting_mode,
            "accounting_configuration_complete": not pricing_blockers,
            "blocking_property_ids": pricing_blockers,
            "optional_property_ids": [
                "pricing.import_network_eur_kwh",
                "pricing.import_levies_eur_kwh",
                "pricing.import_vat_pct",
                "pricing.export_fee_eur_kwh",
            ] if pricing_accounting_mode == "MARKET_ONLY" else [
                "pricing.export_fee_eur_kwh",
            ],
            "configuration_semantics": "market_only_is_valid; partial_import_tariff_fails_closed",
        },
        "metering": {
            "properties": metering_rows,
            "availability": "AVAILABLE",
        },
        "strategy": {
            "configured_properties": strategy_rows,
            "effective_properties": deepcopy(strategy_rows),
            "effective_state": (
                "OVERRIDDEN"
                if any(bool(value) for value in (settings.get("holds") or {}).values())
                else "AVAILABLE"
                if ((source.get("plan") or {}).get("health") in {"OK", "READY"})
                else "NOT_EVALUATED"
            ),
            "effective_reason": (
                "runtime_flexible_load_holds_override_configured_strategy"
                if any(bool(value) for value in (settings.get("holds") or {}).values())
                else "configured_strategy_evaluated_by_current_plan"
                if ((source.get("plan") or {}).get("health") in {"OK", "READY"})
                else "planning_evidence_not_ready"
            ),
            "runtime_overrides": [
                {
                    "override_type": "flexible_load_hold",
                    "target_asset_id": str(asset_id),
                    "active": True,
                }
                for asset_id, active in sorted((settings.get("holds") or {}).items())
                if active
            ],
        },
    }
    canonical_configuration["strategy"]["configured"] = {
        "properties": deepcopy(strategy_rows),
        "status": "AVAILABLE" if strategy_rows else "UNAVAILABLE",
        "reason": None if strategy_rows else "configured_strategy_not_published",
    }
    canonical_configuration["strategy"]["effective"] = {
        "properties": deepcopy(canonical_configuration["strategy"]["effective_properties"]),
        "status": canonical_configuration["strategy"]["effective_state"],
        "reason": canonical_configuration["strategy"]["effective_reason"],
        "runtime_overrides": deepcopy(canonical_configuration["strategy"]["runtime_overrides"]),
    }
    canonical_configuration["strategy"]["profiles"] = _strategy_profile_projection(
        strategy_rows,
        canonical_configuration["strategy"]["effective_properties"],
    )
    canonical_configuration["strategy"]["behavior_topics"] = _strategy_behavior_projection(
        canonical_configuration["strategy"]["profiles"]
    )
    canonical_configuration["strategy"]["participating_assets"] = _settings_participation_projection(source)
    coverage = canonical_coverage(
        objects,
        canonical_configuration,
        model.get("accepted_bindings") or [],
        source.get("semantic_paths") or {},
        source.get("logical_assets") or [],
    )
    commands = _decorate_commands(command_rows)
    activity = [deepcopy(row) for row in (store_data.get("activity") or []) if isinstance(row, dict)][-100:]
    metering_periods = deepcopy(((store_data.get("metering") or {}).get("periods") or {}))
    value_accounting = {
        period_id: interval_actuals(period)
        for period_id, period in metering_periods.items()
        if isinstance(period, dict)
    }
    selected_period = str(settings.get("metering_selected_period") or "today")
    selected_value = deepcopy(value_accounting.get(selected_period) or {})
    metering_projection = _metering_projection(store_data.get("metering") or {}, selected_period)
    planning_projection = _planning_projection(source.get("plan") or {})
    retrospective_projection = _retrospective_projection(
        planning_projection,
        metering_projection,
        store_data.get("command_state") or {},
    )
    unresolved = sum(
        1
        for asset in objects
        for prop in asset.get("properties") or []
        if (prop.get("resolution") or {}).get("status") != "RESOLVED"
    )
    return {
        "kind": "rhi_energy_public_contract",
        "contract_id": "RHI_ENERGY_PUBLIC_CONTRACT_V2",
        "contract_version": PUBLIC_CONTRACT_V2,
        "domain_id": "energy",
        "release": RELEASE,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain_model_revision": model.get("domain_model_revision"),
        "generation": deepcopy(model.get("generation") or {}),
        "layers": {
            "contract_version": model.get("layer_contract_version"),
            "model_fingerprint": model.get("model_fingerprint"),
            "health": deepcopy(source.get("layer_health") or model.get("layer_health") or {}),
            "system_objects": deepcopy(source.get("system_assets") or model.get("system_assets") or []),
            "planning_objects": deepcopy(source.get("planning_assets") or model.get("planning_assets") or []),
            "intelligence_objects": deepcopy(source.get("intelligence_assets") or model.get("intelligence_assets") or []),
            "dependency_diagnostics": deepcopy(model.get("dependency_diagnostics") or {}),
        },
        "health": source.get("health") or "UNKNOWN",
        "core": _build_core(source),
        "objects": objects,
        "profiles": _profile_catalog(),
        "relationships": _relationships(source),
        # Keep the producer-owned physical connection projection available as a
        # first-class V2 surface. Consumers must not reconstruct it from Energy
        # logical objects because charger identity remains Mobility-owned.
        "connections": [
            deepcopy(row) for row in source.get("connections") or []
            if isinstance(row, dict)
        ],
        "configuration": canonical_configuration,
        "coverage": coverage,
        "planning": planning_projection,
        "metering": metering_projection,
        "retrospective": retrospective_projection,
        "intelligence": deepcopy(source.get("intelligence") or {}),
        "overview": deepcopy(source.get("overview") or {}),
        "experience": {
            "presence": deepcopy(source.get("experience_presence") or {}),
            "semantics": (
                "structural_presence_is_independent_of_runtime_availability;"
                "absent_optional_capabilities_are_hidden_from_product_ux"
            ),
        },
        "commands": commands,
        "activity": activity,
        "value_accounting": {
            "selected_period_id": selected_period,
            "selected": selected_value,
            "periods": value_accounting,
            "net_financial_result_eur": selected_value.get("net_financial_result_eur"),
            "net_financial_result": _value_accounting_outcome(selected_period, selected_value),
        },
        "summary": {
            "object_count": len(objects),
            "profile_count": len(_profile_catalog()),
            "property_count": sum(len(asset.get("properties") or []) for asset in objects),
            "control_capability_count": sum(len(asset.get("controls") or []) for asset in objects),
            "executable_control_count": sum(sum(1 for row in asset.get("controls") or [] if row.get("supported") is True) for asset in objects),
            "unresolved_property_count": unresolved,
            "relationship_count": len(_relationships(source)),
            "configuration_property_count": len(pricing_rows) + len(strategy_rows) + len(metering_rows),
            "coverage_complete": coverage.get("complete"),
            "command_count": len(commands),
            "activity_count": len(activity),
            "value_accounting_period_count": len(value_accounting),
            "system_object_count": len(source.get("system_assets") or model.get("system_assets") or []),
            "planning_object_count": len(source.get("planning_assets") or model.get("planning_assets") or []),
            "intelligence_object_count": len(source.get("intelligence_assets") or model.get("intelligence_assets") or []),
            "dependency_edge_count": len(model.get("dependencies") or []),
        },
    }


def published_v2(contract: dict[str, Any]) -> dict[str, Any]:
    """Return an immutable copy of the authoritative Public V2 payload."""
    if contract.get("kind") != "rhi_energy_public_contract" or contract.get("contract_version") != PUBLIC_CONTRACT_V2:
        raise ValueError("unsupported_energy_public_contract")
    return deepcopy(contract)


def public_v2_sensor_attributes(contract: dict[str, Any]) -> dict[str, Any]:
    """Expose the complete canonical V2 payload on the Home Assistant sensor."""
    payload = published_v2(contract)
    return {
        "contract_visibility": "ux_safe",
        "contract_id": "RHI_ENERGY_PUBLIC_CONTRACT_V2",
        **payload,
    }
