"""Logical Energy asset/property factory helpers.

Kept separate from logical_assets.py so canonical composition remains readable and
the runtime projector does not grow into a second semantic authority.
"""
from __future__ import annotations
from typing import Any

try:
    from ..models import LogicalAsset, LogicalProperty
    from ..semantic import object_fact_key, property_definitions
    from .asset_profiles import binding_source, enrich_asset, property_control_metadata
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy
    _root = _Path(__file__).resolve().parents[1]
    _semantic = _runpy.run_path(str(_root / "semantic.py"))
    _asset_profiles = _runpy.run_path(str(_root / "runtime" / "asset_profiles.py"))
    object_fact_key = _semantic["object_fact_key"]
    property_definitions = _semantic["property_definitions"]
    binding_source = _asset_profiles["binding_source"]
    enrich_asset = _asset_profiles["enrich_asset"]
    property_control_metadata = _asset_profiles["property_control_metadata"]
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

