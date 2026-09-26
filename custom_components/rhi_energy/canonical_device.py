"""HA-native projection helpers for canonical Energy devices."""
from __future__ import annotations

from typing import Any

import asyncio

from homeassistant.helpers import device_registry as dr

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


async def sync_canonical_device_topology(hass, entry, assets: list[dict[str, Any]]) -> dict[str, int]:
    """Materialise and reconcile the governed HA device projection in bounded batches.

    Two passes deliberately separate identity creation from relationship assignment so
    child order in the runtime snapshot cannot make Connected devices nondeterministic.
    Only RHI Energy canonical DeviceEntries are mutated here.
    """
    registry = dr.async_get(hass)
    created: dict[str, Any] = {}
    rows = [
        row for row in canonical_projection_assets(assets)
        if row.get("ha_materialization") is True
    ]

    batch_size = 24
    created_count = 0
    parent_update_count = 0
    for offset in range(0, len(rows), batch_size):
        for asset in rows[offset:offset + batch_size]:
            asset_id = str(asset["asset_id"])
            info = canonical_device_info(asset)
            created[asset_id] = registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers=info["identifiers"],
                name=info["name"],
                manufacturer=info["manufacturer"],
                model=info["model"],
                sw_version=info["sw_version"],
            )
            created_count += 1
        # High-cardinality optimizer/panel sites must never monopolise the HA loop.
        await asyncio.sleep(0)

    # RHI semantic composition is intentionally not projected into Home Assistant
    # Device Registry parentage.  Until HA parent/child semantics are mature and
    # stable, canonical Energy devices stay flat and the canonical RHI graph owns
    # all parent/child relationships.  This pass also removes historical links.
    for offset in range(0, len(rows), batch_size):
        for asset in rows[offset:offset + batch_size]:
            asset_id = str(asset["asset_id"])
            device = created.get(asset_id)
            if device is None:
                continue
            if device.via_device_id is not None:
                registry.async_update_device(device.id, via_device_id=None)
                parent_update_count += 1
        await asyncio.sleep(0)
    return {
        "logical_device_count": len(rows),
        "device_reconcile_count": created_count,
        "parent_update_count": parent_update_count,
        "batch_size": batch_size,
    }


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
