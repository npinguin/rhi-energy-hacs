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
                prop["operation_state"] = operation.get("status") or "IDLE"
                prop["operation"] = operation or None
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
        row["operation_state"] = operation.get("status") or "IDLE"
        row["operation"] = operation or None
    return out


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
    source["battery_reserve_write_supported"] = bool(
        (concepts.get("battery_system") or {}).get("reserve_binding")
    )
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
    coverage = canonical_coverage(objects, canonical_configuration)
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
        "objects": objects,
        "profiles": _profile_catalog(),
        "relationships": _relationships(source),
        "configuration": canonical_configuration,
        "coverage": coverage,
        "planning": deepcopy(source.get("plan") or {}),
        "intelligence": deepcopy(source.get("intelligence") or {}),
        "overview": deepcopy(source.get("overview") or {}),
        "commands": deepcopy(command_rows),
        "activity": activity,
        "value_accounting": {
            "selected_period_id": selected_period,
            "selected": selected_value,
            "periods": value_accounting,
            "net_financial_result_eur": selected_value.get("net_financial_result_eur"),
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
            "command_count": len(command_rows),
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
