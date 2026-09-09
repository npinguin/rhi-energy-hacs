"""Small logical Energy object projector.

The compiler already decides which technical candidates are safe and which logical
objects exist.  This module only turns that compiled object inventory into Home
Assistant-facing logical properties and applies runtime values.  It deliberately does
not re-run semantic discovery or integration matching.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

try:
    from ..models import LogicalAsset, LogicalProperty
    from ..semantic import OBJECT_CLASS_LABELS, object_fact_key, property_definitions
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy
    _root = _Path(__file__).resolve().parents[1]
    _semantic = _runpy.run_path(str(_root / "semantic.py"))
    OBJECT_CLASS_LABELS = _semantic["OBJECT_CLASS_LABELS"]
    object_fact_key = _semantic["object_fact_key"]
    property_definitions = _semantic["property_definitions"]
    LogicalAsset = dict  # type: ignore[assignment,misc]
    LogicalProperty = dict  # type: ignore[assignment,misc]


def _hash(value: str, length: int = 10) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:length]


def _bindings(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("binding_id")): row
        for row in (model.get("accepted_bindings") or [])
        if isinstance(row, dict) and row.get("binding_id")
    }


def _source(binding: dict[str, Any] | None) -> dict[str, Any]:
    if not binding:
        return {}
    source = binding.get("source_identity") or {}
    return {
        "binding_id": binding.get("binding_id"),
        "raw_capability_id": binding.get("raw_capability_id"),
        "integration_domain": source.get("integration_domain"),
        "device_registry_id": source.get("device_registry_id"),
        "config_entry_id": source.get("config_entry_id"),
        "entity_registry_id": source.get("entity_registry_id"),
        "current_entity_id": source.get("current_entity_id"),
        "unique_id": source.get("unique_id"),
        "target_scope": source.get("target_scope"),
    }


def _asset(
    asset_id: str,
    object_class: str,
    display_name: str,
    *,
    properties: list[LogicalProperty],
    builder_id: str = "",
    integration_domain: str = "",
    normalization_status: str = "DEGRADED",
    runtime_truth: bool = True,
    parent_asset_id: str | None = None,
    selected_device_ids: list[str] | None = None,
    selection_mode: str | None = None,
    lifecycle_scope: str = "compiled",
    source_domain: str = "energy",
    device_registry_id: str | None = None,
    via_device_registry_id: str | None = None,
) -> LogicalAsset:
    return {
        "asset_id": asset_id,
        "object_class": object_class,
        "asset_type": object_class,
        "display_name": display_name,
        "builder_id": builder_id,
        "integration_domain": integration_domain,
        "selection_mode": selection_mode,
        "selected_device_ids": selected_device_ids or [],
        "normalization_status": normalization_status,
        "runtime_truth": runtime_truth,
        "parent_asset_id": parent_asset_id,
        "properties": properties,
        "health": normalization_status,
        "property_count": len(properties),
        "available_property_count": 0,
        "lifecycle_scope": lifecycle_scope,
        "source_domain": source_domain,
        "device_registry_id": device_registry_id,
        "via_device_registry_id": via_device_registry_id,
    }


def _role_binding(
    roles: dict[str, Any], role: str | None, binding_index: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, list[str]]:
    if not role:
        return None, []
    value = roles.get(role)
    ids = [str(item) for item in (value if isinstance(value, list) else [value] if value else []) if item]
    existing = [binding_index[binding_id] for binding_id in ids if binding_id in binding_index]
    return (existing[0] if existing else None), [str(row.get("binding_id")) for row in existing]


def _properties(
    object_class: str,
    asset_id: str,
    roles: dict[str, Any],
    binding_index: dict[str, dict[str, Any]],
    *,
    aggregate_roles: set[str] | None = None,
    include_roles: set[str] | None = None,
    exclude_roles: set[str] | None = None,
) -> list[LogicalProperty]:
    rows: list[LogicalProperty] = []
    for spec in property_definitions(object_class):
        role = str(spec.get("role") or "") or None
        if include_roles is not None and role not in include_roles:
            continue
        if exclude_roles and role in exclude_roles:
            continue
        binding, binding_ids = _role_binding(roles, role, binding_index)
        derived_from_bound = bool(spec.get("derived") and role and roles.get(role))
        supported = bool(binding_ids or derived_from_bound or (role and aggregate_roles and role in aggregate_roles))
        # Optional capabilities that a concrete asset does not publish are not
        # properties of that asset.  Keeping them as empty rows created misleading
        # UNKNOWN/UNAVAILABLE surfaces throughout diagnostics and HA projection.
        if not supported and not spec.get("required"):
            continue
        status = "NORMALIZED" if binding else "MATCHED" if supported else "MISSING" if spec.get("required") else "UNSUPPORTED"
        property_key = str(spec.get("property_key") or "")
        rows.append(
            {
                "property_key": property_key,
                "display_name": str(spec.get("name") or property_key),
                "unit": spec.get("unit"),
                "kind": str(spec.get("kind") or "text"),
                "platform": str(spec.get("platform") or "sensor"),
                "input_id": spec.get("input_id"),
                "required": bool(spec.get("required")),
                "derived": bool(spec.get("derived") or (role and aggregate_roles and role in aggregate_roles)),
                "status": status,
                "candidate_count": len(binding_ids),
                "binding_ids": binding_ids,
                "issues": [],
                "fact_key": object_fact_key(asset_id, property_key),
                **_source(binding),
            }
        )
    return rows


def _selection(build_inputs: dict[str, dict[str, Any]], builder_id: str) -> dict[str, Any]:
    return (build_inputs.get(builder_id) or {}).get("selection") or {}


def _selected_devices(build_inputs: dict[str, dict[str, Any]], builder_id: str) -> list[str]:
    return [str(value) for value in _selection(build_inputs, builder_id).get("selected_device_ids") or [] if str(value)]


def _build_compiled_assets(
    build_inputs: dict[str, dict[str, Any]],
    model: dict[str, Any],
) -> list[LogicalAsset]:
    concepts = model.get("concepts") or {}
    binding_index = _bindings(model)
    out: list[LogicalAsset] = []

    # Battery: system aggregate + physical units.
    for provider in ((concepts.get("battery_system") or {}).get("providers") or []):
        aid = str(provider.get("asset_id") or "")
        builder = str(provider.get("builder_id") or "")
        integration = str(provider.get("integration_domain") or "")
        if not aid:
            continue
        system_roles = {"reserve": provider.get("reserve_binding")}
        aggregate_roles = {
            role
            for unit in provider.get("units") or []
            for role in (unit.get("bindings") or {})
            if role != "reserve"
        }
        out.append(_asset(
            aid, "battery_system", f"Home Battery System · {integration or aid}",
            builder_id=builder, integration_domain=integration,
            normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
            selection_mode=_selection(build_inputs, builder).get("device_filter_mode"),
            properties=_properties("battery_system", aid, system_roles, binding_index, aggregate_roles=aggregate_roles),
        ))
        for unit in provider.get("units") or []:
            uid = str(unit.get("asset_id") or "")
            if not uid:
                continue
            out.append(_asset(
                uid, "battery_unit", str(unit.get("display_name") or "Battery Unit"),
                builder_id=builder, integration_domain=integration,
                normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                parent_asset_id=aid,
                selected_device_ids=[str(unit.get("device_registry_id"))] if unit.get("device_registry_id") else [],
                device_registry_id=str(unit.get("device_registry_id") or "") or None,
                via_device_registry_id=str(unit.get("via_device_registry_id") or "") or None,
                properties=_properties("battery_system", uid, unit.get("bindings") or {}, binding_index),
            ))

    # One provider object + optional phase children.
    for concept, label in (("grid_connection", "Grid Connection"), ("solar_forecast", "Solar Forecast"), ("price_source", "Energy Price Source")):
        for provider in ((concepts.get(concept) or {}).get("providers") or []):
            if concept == "price_source":
                for source in provider.get("sources") or []:
                    aid = str(source.get("asset_id") or "")
                    builder = str(source.get("builder_id") or provider.get("builder_id") or "")
                    integration = str(source.get("integration_domain") or provider.get("integration_domain") or "")
                    if not aid:
                        continue
                    asset = _asset(
                        aid, concept, str(source.get("display_name") or f"{label} · {integration or aid}"),
                        builder_id=builder, integration_domain=integration,
                        normalization_status=str(source.get("normalization_status") or provider.get("normalization_status") or "DEGRADED"),
                        selection_mode=_selection(build_inputs, builder).get("device_filter_mode"),
                        properties=_properties(concept, aid, source.get("bindings") or {}, binding_index),
                        device_registry_id=str(source.get("device_registry_id") or "") or None,
                    )
                    asset["market_role"] = source.get("market_role")
                    out.append(asset)
                continue
            aid = str(provider.get("asset_id") or "")
            builder = str(provider.get("builder_id") or "")
            integration = str(provider.get("integration_domain") or "")
            if not aid:
                continue
            out.append(_asset(
                aid, concept, f"{label} · {integration or aid}",
                builder_id=builder, integration_domain=integration,
                normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                selection_mode=_selection(build_inputs, builder).get("device_filter_mode"),
                properties=_properties(concept, aid, provider.get("bindings") or {}, binding_index),
            ))
            if concept == "grid_connection":
                for index, phase in enumerate(provider.get("phases") or [], start=1):
                    pid = str(phase.get("asset_id") or "")
                    if not pid:
                        continue
                    out.append(_asset(
                        pid, "grid_phase", f"Grid Phase {index}",
                        builder_id=builder, integration_domain=integration, parent_asset_id=aid,
                        normalization_status="READY" if phase.get("binding") else "DEGRADED",
                        properties=_properties("grid_phase", pid, {"power": phase.get("binding")}, binding_index),
                    ))

    # Solar: aggregate system + inverter and phase children.
    for provider in ((concepts.get("solar_production") or {}).get("providers") or []):
        sid = str(provider.get("asset_id") or "")
        builder = str(provider.get("builder_id") or "")
        integration = str(provider.get("integration_domain") or "")
        if not sid:
            continue
        aggregate_roles = {
            role
            for inverter in provider.get("inverters") or []
            for role in (inverter.get("bindings") or {})
            if role != "phases"
        }
        out.append(_asset(
            sid, "solar_production", f"Solar Production · {integration or sid}",
            builder_id=builder, integration_domain=integration,
            normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
            selection_mode=_selection(build_inputs, builder).get("device_filter_mode"),
            properties=_properties("solar_production", sid, {}, binding_index, aggregate_roles=aggregate_roles),
        ))
        for inverter in provider.get("inverters") or []:
            iid = str(inverter.get("asset_id") or "")
            if not iid:
                continue
            out.append(_asset(
                iid, "solar_inverter", str(inverter.get("display_name") or "Solar Inverter"),
                builder_id=builder, integration_domain=integration, parent_asset_id=sid,
                normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                selected_device_ids=[str(inverter.get("device_registry_id"))] if inverter.get("device_registry_id") else [],
                device_registry_id=str(inverter.get("device_registry_id") or "") or None,
                via_device_registry_id=str(inverter.get("via_device_registry_id") or "") or None,
                properties=_properties("solar_production", iid, inverter.get("bindings") or {}, binding_index),
            ))
            for index, phase in enumerate(inverter.get("phases") or [], start=1):
                pid = str(phase.get("asset_id") or "")
                if pid:
                    out.append(_asset(
                        pid, "solar_inverter_phase", f"Solar Inverter Phase {index}",
                        builder_id=builder, integration_domain=integration, parent_asset_id=iid,
                        normalization_status="READY" if phase.get("binding") else "DEGRADED",
                        properties=_properties("solar_inverter_phase", pid, {"power": phase.get("binding")}, binding_index),
                    ))

    # Device collections.
    for provider in ((concepts.get("gas_meter") or {}).get("providers") or []):
        builder = str(provider.get("builder_id") or "")
        integration = str(provider.get("integration_domain") or "")
        for meter in provider.get("meters") or []:
            aid = str(meter.get("asset_id") or "")
            if aid:
                out.append(_asset(
                    aid, "gas_meter", str(meter.get("display_name") or "Gas Meter"),
                    builder_id=builder, integration_domain=integration,
                    normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                    selected_device_ids=[str(meter.get("device_registry_id"))] if meter.get("device_registry_id") else [],
                    device_registry_id=str(meter.get("device_registry_id") or "") or None,
                    via_device_registry_id=str(meter.get("via_device_registry_id") or "") or None,
                    properties=_properties("gas_meter", aid, meter.get("bindings") or {"total": meter.get("binding")}, binding_index),
                ))
    for provider in ((concepts.get("solar_optimizer") or {}).get("providers") or []):
        builder = str(provider.get("builder_id") or "")
        integration = str(provider.get("integration_domain") or "")
        for optimizer in provider.get("optimizers") or []:
            aid = str(optimizer.get("asset_id") or "")
            if aid:
                out.append(_asset(
                    aid, "solar_optimizer", str(optimizer.get("display_name") or "Solar Optimizer"),
                    builder_id=builder, integration_domain=integration,
                    normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                    selected_device_ids=[str(optimizer.get("device_registry_id"))] if optimizer.get("device_registry_id") else [],
                    device_registry_id=str(optimizer.get("device_registry_id") or "") or None,
                    via_device_registry_id=str(optimizer.get("via_device_registry_id") or "") or None,
                    properties=_properties("solar_optimizer", aid, optimizer.get("bindings") or {}, binding_index),
                ))
    return out


def build_logical_assets(build_inputs: dict[str, dict[str, Any]], model: dict[str, Any]) -> list[LogicalAsset]:
    out = _build_compiled_assets(build_inputs, model)
    dedup: dict[str, LogicalAsset] = {}
    for asset in out:
        asset_id = str(asset.get("asset_id") or "")
        if asset_id and (asset_id not in dedup or (asset.get("runtime_truth") and not dedup[asset_id].get("runtime_truth"))):
            dedup[asset_id] = asset
    return [dedup[key] for key in sorted(dedup)]


def _runtime_only_assets(flexible_assets: list[dict[str, Any]]) -> list[LogicalAsset]:
    home_spec = property_definitions("home_consumption")[0]
    rows: list[LogicalAsset] = [_asset(
        "home_consumption", "home_consumption", "Home Consumption",
        normalization_status="READY", runtime_truth=True, lifecycle_scope="runtime_derived", source_domain="energy",
        properties=[{
            "property_key": str(home_spec["property_key"]), "display_name": str(home_spec["name"]),
            "unit": home_spec.get("unit"), "kind": str(home_spec.get("kind") or "power"),
            "platform": "sensor", "input_id": None, "required": True, "derived": True,
            "status": "MATCHED", "candidate_count": 0, "issues": [], "fact_key": "home_consumption.power_kw",
        }],
    )]
    for item in flexible_assets:
        source_id = str(item.get("asset_id") or "")
        if not source_id:
            continue
        props: list[LogicalProperty] = []
        for spec in property_definitions("flexible_load"):
            key = str(spec.get("property_key") or "")
            if item.get(key) is None:
                continue
            props.append({
                "property_key": key, "display_name": str(spec.get("name") or key),
                "unit": spec.get("unit"), "kind": str(spec.get("kind") or "text"), "platform": "sensor",
                "input_id": None, "required": False, "derived": False,
                "status": "NORMALIZED",
                "candidate_count": 0, "issues": [], "fact_key": f"flexible:{source_id}:{key}",
            })
        rows.append(_asset(
            f"flexible_load_{_hash(source_id)}", "flexible_load",
            str(item.get("display_name") or source_id),
            integration_domain=str(item.get("source_domain") or "mobility"), normalization_status="READY",
            runtime_truth=True, lifecycle_scope="producer_runtime", source_domain=str(item.get("source_domain") or "mobility"),
            selected_device_ids=[str(item.get("device_id"))] if item.get("device_id") else [], properties=props,
        ))
    return rows


def apply_runtime_values(
    logical_assets: list[dict[str, Any]],
    facts: dict[str, Any],
    flexible_assets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = deepcopy(logical_assets) + _runtime_only_assets(flexible_assets or [])
    flexible_by_logical = {
        f"flexible_load_{_hash(str(item.get('asset_id') or ''))}": item
        for item in (flexible_assets or []) if item.get("asset_id")
    }
    for asset in rows:
        available = 0
        missing_required = 0
        flexible = flexible_by_logical.get(str(asset.get("asset_id") or ""))
        for prop in asset.get("properties") or []:
            value = flexible.get(prop.get("property_key")) if flexible is not None else facts.get(prop.get("fact_key")) if prop.get("fact_key") else None
            prop["value"] = value
            prop["availability"] = "AVAILABLE" if value is not None else "UNAVAILABLE"
            if value is not None:
                available += 1
                if asset.get("runtime_truth"):
                    prop["status"] = "NORMALIZED"
            elif prop.get("required") and asset.get("runtime_truth"):
                missing_required += 1
        if asset.get("runtime_truth"):
            asset["health"] = "DEGRADED" if missing_required or not available else "OK"
        else:
            asset["health"] = asset.get("normalization_status") or "UNKNOWN"
        asset["property_count"] = len(asset.get("properties") or [])
        asset["available_property_count"] = available
    return rows
