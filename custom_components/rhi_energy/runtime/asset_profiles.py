"""Bounded Energy logical-asset profile and solar-panel enrichment.

Logical asset construction stays in runtime/logical_assets.py. This module owns only
profile/capability/visual decoration and the evidence-backed panel child shape.
"""
from __future__ import annotations

import hashlib
from typing import Any

try:
    from ..profile_catalog import profile_context
    from ..visual_catalog import resolve_visual_ref
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy
    _root = _Path(__file__).resolve().parents[1]
    profile_context = _runpy.run_path(str(_root / "profile_catalog.py"))["profile_context"]
    resolve_visual_ref = _runpy.run_path(str(_root / "visual_catalog.py"))["resolve_visual_ref"]


def binding_index(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("binding_id")): row
        for row in (model.get("accepted_bindings") or [])
        if isinstance(row, dict) and row.get("binding_id")
    }


def binding_device_ids(
    role_map: dict[str, Any],
    binding_index: dict[str, dict[str, Any]],
) -> list[str]:
    ids: list[str] = []
    for value in role_map.values():
        for binding_id in (value if isinstance(value, list) else [value] if value else []):
            source = (binding_index.get(str(binding_id)) or {}).get("source_identity") or {}
            device_id = str(source.get("device_registry_id") or "")
            if device_id and device_id not in ids:
                ids.append(device_id)
    return ids


def binding_source(binding: dict[str, Any] | None) -> dict[str, Any]:
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


def property_control_metadata(spec: dict[str, Any], binding: dict[str, Any] | None) -> dict[str, Any]:
    technical = (binding or {}).get("technical_capability") or {}
    platform = str(spec.get("platform") or "sensor")
    writable = bool(binding and technical.get("writable") is True)
    editable = bool(spec.get("editable") and writable)
    readback_safe = editable and platform in {"number", "select", "switch"}
    return {
        "editable": readback_safe,
        "editor": spec.get("editor") if writable else None,
        "write_supported": readback_safe,
        "control_capability": writable,
        "control_reason": (
            "authoritative_state_readback_available"
            if readback_safe
            else "action_readback_not_defined"
            if writable and platform == "button"
            else None
        ),
        "technical_capability": technical,
    }


_TYPE_CAPABILITIES: dict[str, set[str]] = {
    "battery_system": {"stores_energy"},
    "battery": {"stores_energy"},
    "solar_production": {"produces_energy"},
    "solar_inverter": {"produces_energy"},
    "solar_optimizer_site": {"produces_energy", "aggregates_optimizers"},
    "solar_zone": {"produces_energy", "aggregates_optimizers"},
    "solar_optimizer": {"produces_energy"},
    "solar_panel": {"produces_energy"},
    "grid_connection": {"imports_energy", "exports_energy"},
    "home_consumption": {"consumes_energy"},
    "flexible_load": {"consumes_energy"},
    "solar_forecast": {"forecastable"},
}


def identity(row: dict[str, Any] | None) -> dict[str, Any]:
    row = row or {}
    return {
        "brand": row.get("brand") or row.get("manufacturer"),
        "model": row.get("model"),
        "variant": row.get("variant"),
        "model_year": row.get("model_year"),
    }


def enrich_asset(asset: dict[str, Any]) -> dict[str, Any]:
    properties = list(asset.get("properties") or [])
    asset_type = str(asset.get("asset_type") or asset.get("object_class") or "")
    caps = set(_TYPE_CAPABILITIES.get(asset_type, set()))
    keys = {str(row.get("property_key") or "") for row in properties}
    if any("power" in key for key in keys):
        caps.add("measures_power")
    if any("energy" in key for key in keys):
        caps.add("measures_energy")
    if any("soc" in key for key in keys):
        caps.add("measures_soc")
    if any("reserve" in key for key in keys):
        caps.add("supports_reserve")
    if any(bool(row.get("write_supported")) for row in properties):
        caps.add("controllable")
    context = profile_context(asset)
    if not asset.get("profile_id"):
        asset["profile_id"] = context.get("profile_id")
    asset["technical_specification"] = context.get("technical_specification") or {}
    asset["capabilities"] = sorted(caps | set(context.get("profile_capabilities") or []))
    asset["visual_ref"] = resolve_visual_ref(
        asset_type, asset.get("visual_ref"), context.get("profile_visual_ref")
    )
    return asset


def solar_panel_asset(
    *,
    optimizer_asset_id: str,
    panel_binding_id: str,
    binding: dict[str, Any] | None,
    builder_id: str,
    integration_domain: str,
    normalization_status: str,
) -> dict[str, Any]:
    source = (binding or {}).get("source_identity") or {}
    digest = hashlib.sha256(
        f"{optimizer_asset_id}|{panel_binding_id}".encode()
    ).hexdigest()[:10]
    asset = {
        "asset_id": f"solar_panel_{digest}",
        "object_class": "solar_panel",
        "asset_type": "solar_panel",
        "display_name": "Solar Panel",
        "builder_id": builder_id,
        "integration_domain": integration_domain,
        "selection_mode": None,
        "selected_device_ids": [],
        "normalization_status": normalization_status,
        "runtime_truth": True,
        "parent_asset_id": optimizer_asset_id,
        "properties": [{
            "property_key": "solar_panel.identity",
            "display_name": "Panel identity",
            "unit": None,
            "kind": "text",
            "platform": "sensor",
            "input_id": "panel_identity",
            "required": False,
            "derived": False,
            "status": "NORMALIZED" if binding else "UNSUPPORTED",
            "candidate_count": 1 if binding else 0,
            "binding_ids": [panel_binding_id] if binding else [],
            "issues": [],
            "fact_key": f"{optimizer_asset_id}.panel_identity",
            "binding_id": panel_binding_id,
            "raw_capability_id": (binding or {}).get("raw_capability_id"),
            "integration_domain": source.get("integration_domain"),
            "device_registry_id": source.get("device_registry_id"),
            "config_entry_id": source.get("config_entry_id"),
            "entity_registry_id": source.get("entity_registry_id"),
            "current_entity_id": source.get("current_entity_id"),
            "unique_id": source.get("unique_id"),
            "target_scope": source.get("target_scope"),
        }],
        "health": normalization_status,
        "property_count": 1,
        "available_property_count": 0,
        "lifecycle_scope": "accepted",
        "source_domain": "energy",
        "device_registry_id": None,
        "via_device_registry_id": None,
        "identity": {},
    }
    return enrich_asset(asset)
