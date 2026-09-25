"""Canonical Energy composition helpers.

Stable composition metadata only. This module does not inspect Home Assistant registries,
source integrations or runtime values.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


TOP_LEVEL_CANONICAL_CLASSES = {
    "grid_connection",
    "solar_production",
    "battery_system",
    "solar_optimizer_site",
    "home_consumption",
    "gas_meter",
}


STRUCTURAL_CANONICAL_ASSETS: tuple[dict[str, Any], ...] = (
    {
        "asset_id": "energy_site",
        "object_class": "energy_site",
        "asset_type": "energy_site",
        "display_name": "Energy Site",
        "parent_asset_id": None,
        "lifecycle_scope": "canonical_structure",
        "runtime_truth": False,
        "properties": [],
    },
    {
        "asset_id": "flexible_loads",
        "object_class": "flexible_loads",
        "asset_type": "flexible_loads",
        "display_name": "Flexible Loads",
        "parent_asset_id": "energy_site",
        "lifecycle_scope": "canonical_structure",
        "runtime_truth": False,
        "properties": [],
    },
)


def canonical_parent_asset_id(asset: dict[str, Any]) -> str | None:
    """Return governed canonical parent without mutating runtime/domain truth."""
    explicit = str(asset.get("parent_asset_id") or "")
    if explicit:
        return explicit
    object_class = str(asset.get("object_class") or asset.get("asset_type") or "")
    if object_class in TOP_LEVEL_CANONICAL_CLASSES:
        return "energy_site"
    if object_class == "flexible_load":
        return "flexible_loads"
    return None


def canonical_projection_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the HA composition view without polluting source-backed runtime inventory."""
    rows = [deepcopy(row) for row in STRUCTURAL_CANONICAL_ASSETS]
    for asset in assets:
        if not isinstance(asset, dict) or not asset.get("asset_id"):
            continue
        row = deepcopy(asset)
        row["parent_asset_id"] = canonical_parent_asset_id(row)
        rows.append(row)

    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        asset_id = str(row.get("asset_id") or "")
        if asset_id:
            dedup[asset_id] = row
    return [dedup[key] for key in sorted(dedup)]
