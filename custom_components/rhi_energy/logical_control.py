"""Shared helpers for native controls on canonical Energy devices."""
from __future__ import annotations

from typing import Any

from .canonical_device import canonical_device_info


def logical_asset(runtime, asset_id: str) -> dict[str, Any]:
    return next(
        (
            row
            for row in runtime.snapshot.get("logical_assets") or []
            if str(row.get("asset_id") or "") == asset_id
        ),
        {},
    )


def logical_property(runtime, asset_id: str, property_key: str) -> dict[str, Any]:
    asset = logical_asset(runtime, asset_id)
    return next(
        (
            row
            for row in asset.get("properties") or []
            if str(row.get("property_key") or "") == property_key
        ),
        {},
    )


def supported_controls(runtime, platform: str) -> dict[str, tuple[str, str]]:
    desired: dict[str, tuple[str, str]] = {}
    for asset in runtime.snapshot.get("logical_assets") or []:
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id:
            continue
        for prop in asset.get("properties") or []:
            property_key = str(prop.get("property_key") or "")
            if (
                property_key
                and str(prop.get("platform") or "") == platform
                and prop.get("write_supported") is True
            ):
                uid = f"rhi_energy:logical:{asset_id}:control:{property_key}"
                desired[uid] = (asset_id, property_key)
    return desired


def supported_actions(runtime) -> dict[str, tuple[str, str]]:
    """Return bound canonical stateless actions for native HA button projection."""
    desired: dict[str, tuple[str, str]] = {}
    for asset in runtime.snapshot.get("logical_assets") or []:
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id:
            continue
        for prop in asset.get("properties") or []:
            property_key = str(prop.get("property_key") or "")
            binding_ids = [
                str(value) for value in (prop.get("binding_ids") or []) if value
            ]
            if prop.get("binding_id"):
                binding_ids.append(str(prop.get("binding_id")))
            if (
                property_key
                and str(prop.get("platform") or "") == "button"
                and str(prop.get("kind") or "") == "action"
                and len(set(binding_ids)) == 1
            ):
                uid = f"rhi_energy:logical:{asset_id}:action:{property_key}"
                desired[uid] = (asset_id, property_key)
    return desired


def control_device_info(runtime, asset_id: str) -> dict[str, Any]:
    return canonical_device_info(logical_asset(runtime, asset_id) or {"asset_id": asset_id})


def source_state(hass, prop: dict[str, Any]):
    entity_id = str(prop.get("current_entity_id") or "")
    return hass.states.get(entity_id) if entity_id else None
