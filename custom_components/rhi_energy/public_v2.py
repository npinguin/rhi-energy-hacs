"""Canonical Energy public contract V2 and the V1 compatibility boundary."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

try:
    from .const import RELEASE
    from .profile_catalog import EnergyProfileCatalogProvider, profile_context
    from .visual_catalog import resolve_visual_ref
    from .runtime.canonical_semantics import pricing_properties, strategy_properties
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
        "v1_fallback_allowed": False,
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


def _decorate_objects(
    objects: list[dict[str, Any]],
    property_operations: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    operation_rows = property_operations or {}
    for raw in objects:
        if not isinstance(raw, dict):
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
        asset["visual_ref"] = resolve_visual_ref(
            asset_type,
            asset.get("visual_ref"),
            context.get("profile_visual_ref"),
        )
        asset["property_publication"] = _publication(asset)
        provenance_rows: list[dict[str, Any]] = []
        for property_row in asset.get("properties") or []:
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
    """Expose stable D0/D1 planning outcomes from the canonical planner only."""
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
            "planning_outcome_incomplete"
            if raw
            else "planning_horizon_missing"
        )
        horizons[horizon_id] = {
            "required_kwh": required,
            "planned_kwh": planned,
            "executed_kwh": None,
            "still_to_plan_kwh": still,
            "flexible_required_kwh": flexible_required,
            "flexible_planned_kwh": flexible_planned,
            "flexible_executed_kwh": None,
            "flexible_still_to_plan_kwh": flexible_still,
            "status": status,
            "reason": reason,
            "execution_status": "NOT_MEASURED",
            "execution_reason": "advisory_plan_has_no_authoritative_execution_meter",
            "quality": deepcopy(quality),
            "source_refs": deepcopy(raw.get("source_refs") or []),
        }
    return {
        "plan_id": plan.get("plan_id"),
        "generated_at": plan.get("generated_at"),
        "health": plan.get("health") or "UNKNOWN",
        "reason": plan.get("reason"),
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
        "contract_id": "RHI_ENERGY_CORE_V1",
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
    logical_assets = [item for item in snapshot.get("logical_assets") or [] if isinstance(item, dict)]
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
        source = relation.get("source_asset_id") or relation.get("from_asset_id") or relation.get("source")
        target = relation.get("target_asset_id") or relation.get("to_asset_id") or relation.get("target")
        if not source or not target:
            continue
        relationship_id = str(relation.get("relationship_id") or f"external:{index}:{source}:{target}")
        rows[relationship_id] = {
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
        row["operation"] = public_operation
    return out


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
    """Build one object-centric contract from resolved runtime truth.

    ``_compatibility`` is an internal lossless envelope used only by the V1 facade.
    It is stripped from the published V2 payload and prevents the facade from reading
    mutable runtime state through a second path.
    """
    source = deepcopy(snapshot)
    source["settings"] = deepcopy(store_data.get("settings") or {})
    concepts = model.get("concepts") or {}
    source["battery_reserve_write_supported"] = _battery_reserve_write_supported(concepts)
    property_operations = deepcopy(store_data.get("property_operation_state") or {})
    objects = _decorate_objects(
        deepcopy(source.get("logical_assets") or []),
        property_operations,
    )
    settings = deepcopy(store_data.get("settings") or {})
    pricing_rows = _apply_configuration_operation_state(
        pricing_properties(source.get("facts") or {}, settings),
        property_operations,
    )
    strategy_rows = _apply_configuration_operation_state(
        strategy_properties(settings),
        property_operations,
    )
    canonical_configuration = {
        "pricing": {
            "properties": pricing_rows,
            "availability": "AVAILABLE" if any(row.get("availability") == "AVAILABLE" for row in pricing_rows) else "UNAVAILABLE",
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
    coverage = canonical_coverage(objects, canonical_configuration)
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
        "configuration": canonical_configuration,
        "coverage": coverage,
        "planning": _planning_projection(source.get("plan") or {}),
        "intelligence": deepcopy(source.get("intelligence") or {}),
        "overview": deepcopy(source.get("overview") or {}),
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
            "configuration_property_count": len(pricing_rows) + len(strategy_rows),
            "coverage_complete": coverage.get("complete"),
            "command_count": len(commands),
            "activity_count": len(activity),
            "value_accounting_period_count": len(value_accounting),
            "system_object_count": len(source.get("system_assets") or model.get("system_assets") or []),
            "planning_object_count": len(source.get("planning_assets") or model.get("planning_assets") or []),
            "intelligence_object_count": len(source.get("intelligence_assets") or model.get("intelligence_assets") or []),
            "dependency_edge_count": len(model.get("dependencies") or []),
        },
        "_compatibility": source,
    }


def published_v2(contract: dict[str, Any]) -> dict[str, Any]:
    """Return the public payload without the private V1 reconstruction envelope."""
    return {key: deepcopy(value) for key, value in contract.items() if key != "_compatibility"}


def compatibility_snapshot(contract: dict[str, Any]) -> dict[str, Any]:
    """Return the exact V1 source snapshot carried by one immutable V2 decision."""
    if contract.get("kind") != "rhi_energy_public_contract" or contract.get("contract_version") != PUBLIC_CONTRACT_V2:
        raise ValueError("unsupported_energy_public_contract")
    source = contract.get("_compatibility")
    if not isinstance(source, dict):
        raise ValueError("energy_v2_compatibility_envelope_missing")
    return deepcopy(source)


def public_v2_sensor_attributes(contract: dict[str, Any]) -> dict[str, Any]:
    """Expose the complete canonical V2 payload on the Home Assistant sensor."""
    payload = published_v2(contract)
    return {
        "contract_visibility": "ux_safe",
        "contract_id": "RHI_ENERGY_PUBLIC_CONTRACT_V2",
        **payload,
    }
