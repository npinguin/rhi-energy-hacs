"""HA-native projection helpers for canonical Energy devices."""
from __future__ import annotations

from typing import Any

from .const import DOMAIN, RELEASE
from .runtime.canonical_structure import canonical_parent_asset_id
from .semantic import OBJECT_CLASS_LABELS


def canonical_device_identifier(asset_id: str) -> tuple[str, str]:
    return (DOMAIN, f"logical:{asset_id}")


def canonical_device_info(asset: dict[str, Any]) -> dict[str, Any]:
    """Return one canonical HA DeviceInfo shape with declarative parentage.

    Only RHI canonical identifiers are linked. Physical source devices remain owned by
    their source integrations and no Device Registry scan or mutation happens here.
    """
    asset_id = str(asset.get("asset_id") or "")
    object_class = str(asset.get("object_class") or asset.get("asset_type") or "logical_object")
    info: dict[str, Any] = {
        "identifiers": {canonical_device_identifier(asset_id)},
        "name": asset.get("display_name") or asset_id.replace("_", " ").title(),
        "manufacturer": "Robotix Home Intelligence",
        "model": f"Energy canonical object · {OBJECT_CLASS_LABELS.get(object_class, object_class.replace('_', ' ').title())}",
        "sw_version": RELEASE,
    }
    parent_asset_id = canonical_parent_asset_id(asset)
    if parent_asset_id:
        info["via_device"] = canonical_device_identifier(parent_asset_id)
    return info


def source_device_ids(asset: dict[str, Any]) -> list[str]:
    """Return exact physical source-device provenance without creating HA topology."""
    values: list[str] = []
    for value in asset.get("selected_device_ids") or []:
        if value and str(value) not in values:
            values.append(str(value))
    direct = asset.get("device_registry_id")
    if direct and str(direct) not in values:
        values.append(str(direct))
    for prop in asset.get("properties") or []:
        value = prop.get("device_registry_id")
        if value and str(value) not in values:
            values.append(str(value))
    return values
