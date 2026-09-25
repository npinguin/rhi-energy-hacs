"""Small logical Energy object projector.

Semantic acceptance already decides which technical candidates are safe and which logical
objects exist.  This module only turns that accepted object inventory into Home
Assistant-facing logical properties and applies runtime values.  It deliberately does
not re-run semantic discovery or integration matching.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from ..models import LogicalAsset, LogicalProperty
    from ..semantic import object_fact_key, property_definitions
    from .asset_profiles import binding_device_ids, binding_index as build_binding_index, binding_source, enrich_asset, identity, property_control_metadata, solar_panel_asset
    from .optimizer_topology import optimizer_descriptors
    from .resolution import compatibility_availability, resolve_property
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy
    _root = _Path(__file__).resolve().parents[1]
    _semantic = _runpy.run_path(str(_root / "semantic.py"))
    _asset_profiles = _runpy.run_path(str(_root / "runtime" / "asset_profiles.py"))
    build_binding_index = _asset_profiles["binding_index"]
    binding_source = _asset_profiles["binding_source"]
    binding_device_ids = _asset_profiles["binding_device_ids"]
    property_control_metadata = _asset_profiles["property_control_metadata"]
    enrich_asset = _asset_profiles["enrich_asset"]
    identity = _asset_profiles["identity"]
    solar_panel_asset = _asset_profiles["solar_panel_asset"]
    optimizer_descriptors = _runpy.run_path(str(_root / "runtime" / "optimizer_topology.py"))["optimizer_descriptors"]
    object_fact_key = _semantic["object_fact_key"]
    property_definitions = _semantic["property_definitions"]
    _resolution = _runpy.run_path(str(_root / "runtime" / "resolution.py"))
    compatibility_availability = _resolution["compatibility_availability"]
    resolve_property = _resolution["resolve_property"]
    LogicalAsset = dict  # type: ignore[assignment,misc]
    LogicalProperty = dict  # type: ignore[assignment,misc]


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
    lifecycle_scope: str = "accepted",
    source_domain: str = "energy",
    device_registry_id: str | None = None,
    via_device_registry_id: str | None = None,
    identity: dict[str, Any] | None = None,
    profile_id: str | None = None,
    visual_ref: str | None = None,
) -> LogicalAsset:
    asset: LogicalAsset = {
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
        "identity": identity or {},
        "profile_id": profile_id,
        "visual_ref": visual_ref,
    }
    return enrich_asset(asset)


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
) -> list[LogicalProperty]:
    rows: list[LogicalProperty] = []
    for spec in property_definitions(object_class):
        role = str(spec.get("role") or "") or None
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
        rows.append({
            "property_key": property_key, "display_name": str(spec.get("name") or property_key),
            "unit": spec.get("unit"), "kind": str(spec.get("kind") or "text"),
            "platform": str(spec.get("platform") or "sensor"), "input_id": spec.get("input_id"),
            "required": bool(spec.get("required")),
            "derived": bool(spec.get("derived") or (role and aggregate_roles and role in aggregate_roles)),
            "status": status, "candidate_count": len(binding_ids), "binding_ids": binding_ids,
            "issues": [], "fact_key": None if str(spec.get("kind") or "") == "action" else object_fact_key(asset_id, property_key),
            **property_control_metadata(spec, binding), **binding_source(binding),
        })
    return rows


def _selection(build_inputs: dict[str, dict[str, Any]], builder_id: str) -> dict[str, Any]:
    return (build_inputs.get(builder_id) or {}).get("selection") or {}


def _build_domain_assets(
    build_inputs: dict[str, dict[str, Any]],
    model: dict[str, Any],
) -> list[LogicalAsset]:
    concepts = model.get("concepts") or {}
    binding_index = build_binding_index(model)
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
            selected_device_ids=[
                str(unit.get("device_registry_id"))
                for unit in provider.get("units") or []
                if unit.get("device_registry_id")
            ],
            properties=_properties("battery_system", aid, system_roles, binding_index, aggregate_roles=aggregate_roles),
        ))
        for unit in provider.get("units") or []:
            uid = str(unit.get("asset_id") or "")
            if not uid:
                continue
            out.append(_asset(
                uid, "battery", str(unit.get("display_name") or "Battery"),
                builder_id=builder, integration_domain=integration,
                normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                parent_asset_id=aid,
                selected_device_ids=[str(unit.get("device_registry_id"))] if unit.get("device_registry_id") else [],
                device_registry_id=str(unit.get("device_registry_id") or "") or None,
                via_device_registry_id=str(unit.get("via_device_registry_id") or "") or None,
                identity=identity(unit),
                properties=_properties("battery", uid, unit.get("bindings") or {}, binding_index),
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
            provider_roles = provider.get("bindings") or {}
            out.append(_asset(
                aid, concept, f"{label} · {integration or aid}",
                builder_id=builder, integration_domain=integration,
                normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                selection_mode=_selection(build_inputs, builder).get("device_filter_mode"),
                selected_device_ids=binding_device_ids(provider_roles, binding_index),
                properties=_properties(concept, aid, provider_roles, binding_index),
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
            selected_device_ids=[
                str(inverter.get("device_registry_id"))
                for inverter in provider.get("inverters") or []
                if inverter.get("device_registry_id")
            ],
            properties=_properties("solar_production", sid, {}, binding_index, aggregate_roles=aggregate_roles),
        ))
        for inverter in provider.get("inverters") or []:
            iid = str(inverter.get("asset_id") or "")
            if not iid:
                continue
            inverter_asset = _asset(
                iid, "solar_inverter", str(inverter.get("display_name") or "Solar Inverter"),
                builder_id=builder, integration_domain=integration, parent_asset_id=sid,
                normalization_status=str(provider.get("normalization_status") or "DEGRADED"),
                selected_device_ids=[str(inverter.get("device_registry_id"))] if inverter.get("device_registry_id") else [],
                device_registry_id=str(inverter.get("device_registry_id") or "") or None,
                via_device_registry_id=str(inverter.get("via_device_registry_id") or "") or None,
                identity=identity(inverter),
                properties=_properties("solar_production", iid, inverter.get("bindings") or {}, binding_index),
            )
            inverter_asset["linked_battery_asset_ids"] = [
                str(value)
                for value in inverter.get("linked_battery_asset_ids") or []
                if value
            ]
            inverter_asset["battery_correction_required"] = bool(
                inverter.get("battery_correction_required")
            )
            inverter_asset["battery_linkage_resolution"] = str(
                inverter.get("battery_linkage_resolution") or "not_required"
            )
            out.append(inverter_asset)
            for index, phase in enumerate(inverter.get("phases") or [], start=1):
                pid = str(phase.get("asset_id") or "")
                if pid:
                    phase_bindings = phase.get("bindings") or (
                        {"power": phase.get("binding")} if phase.get("binding") else {}
                    )
                    out.append(_asset(
                        pid,
                        "solar_inverter_phase",
                        f"Solar Inverter Phase {phase.get('phase') or index}",
                        builder_id=builder,
                        integration_domain=integration,
                        parent_asset_id=iid,
                        normalization_status="READY" if phase_bindings else "DEGRADED",
                        properties=_properties(
                            "solar_inverter_phase", pid, phase_bindings, binding_index
                        ),
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
                    identity=identity(meter),
                    properties=_properties("gas_meter", aid, meter.get("bindings") or {"total": meter.get("binding")}, binding_index),
                ))
    for provider in ((concepts.get("solar_optimizer") or {}).get("providers") or []):
        builder, integration = str(provider.get("builder_id") or ""), str(provider.get("integration_domain") or "")
        health = str(provider.get("normalization_status") or "DEGRADED")
        for descriptor in optimizer_descriptors(provider):
            row, object_class = descriptor["row"], str(descriptor["object_class"])
            aid = str(row.get("asset_id") or "")
            out.append(_asset(
                aid, object_class, str(descriptor["display_name"]), builder_id=builder,
                integration_domain=integration, normalization_status=health,
                parent_asset_id=descriptor.get("parent_asset_id"),
                selected_device_ids=[str(row["device_registry_id"])] if row.get("device_registry_id") else [],
                device_registry_id=str(row.get("device_registry_id") or "") or None,
                via_device_registry_id=str(row.get("via_device_registry_id") or "") or None,
                identity=identity(row), properties=_properties(object_class, aid, row.get("bindings") or {}, binding_index),
            ))
            if descriptor.get("panel_binding"):
                panel_binding = str(descriptor["panel_binding"])
                out.append(solar_panel_asset(
                    optimizer_asset_id=aid, panel_binding_id=panel_binding,
                    binding=binding_index.get(panel_binding), builder_id=builder,
                    integration_domain=integration, normalization_status=health,
                ))
    return out

def build_logical_assets(build_inputs: dict[str, dict[str, Any]], model: dict[str, Any]) -> list[LogicalAsset]:
    out = _build_domain_assets(build_inputs, model)
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
        parent_asset_id="energy_site",
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
        provenance = item.get("source_provenance") if isinstance(item.get("source_provenance"), dict) else {}
        source_device_id = str(
            item.get("device_registry_id")
            or item.get("device_id")
            or provenance.get("device_registry_id")
            or provenance.get("device_id")
            or ""
        ) or None
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
        asset = _asset(
            source_id, "flexible_load",
            str(item.get("display_name") or source_id),
            integration_domain=str(item.get("source_domain") or "mobility"), normalization_status="READY",
            runtime_truth=True, lifecycle_scope="producer_runtime", source_domain=str(item.get("source_domain") or "mobility"),
            parent_asset_id="flexible_loads",
            selected_device_ids=[source_device_id] if source_device_id else [],
            device_registry_id=source_device_id,
            properties=props,
        )
        # Producer/domain conclusions stay explicit; UX never reconstructs them.
        asset["participation_state"] = item.get("participation_state")
        asset["operating_state"] = item.get("operating_state")
        asset["availability_state"] = item.get("availability_state")
        asset["visual_ref"] = item.get("visual_ref")
        asset["producer_asset_type"] = item.get("source_asset_kind") or item.get("asset_type")
        rows.append(asset)
    return rows


def apply_runtime_values(
    logical_assets: list[dict[str, Any]],
    facts: dict[str, Any],
    flexible_assets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = deepcopy(logical_assets) + _runtime_only_assets(flexible_assets or [])
    flexible_by_logical = {
        str(item.get("asset_id")): item
        for item in (flexible_assets or []) if item.get("asset_id")
    }
    for asset in rows:
        available = 0
        missing_required = 0
        flexible = flexible_by_logical.get(str(asset.get("asset_id") or ""))
        for prop in asset.get("properties") or []:
            value = flexible.get(prop.get("property_key")) if flexible is not None else facts.get(prop.get("fact_key")) if prop.get("fact_key") else None
            prop["value"] = value
            resolution = resolve_property(
                prop,
                value,
                value_revision=int(asset.get("value_revision") or 1),
            )
            prop["resolution"] = resolution
            prop["availability"] = compatibility_availability(resolution)
            if resolution["status"] == "RESOLVED":
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
