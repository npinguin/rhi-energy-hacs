"""HA-native projection helpers for canonical Energy devices."""
from __future__ import annotations

from typing import Any

from .const import DOMAIN, RELEASE
from .runtime.canonical_structure import canonical_projection_assets
from .semantic import OBJECT_CLASS_LABELS


def canonical_device_identifier(asset_id: str) -> tuple[str, str]:
    return (DOMAIN, f"logical:{asset_id}")


def canonical_device_info(asset: dict[str, Any]) -> dict[str, Any]:
    """Return one canonical HA DeviceInfo shape without semantic HA parentage.

    Energy canonical composition remains in the canonical graph/relationship contract.
    Home Assistant registry parentage is not used for semantic composition.
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
