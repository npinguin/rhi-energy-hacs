"""Canonical Energy composition helpers.

Stable composition metadata only. This module does not inspect Home Assistant registries,
source integrations or runtime values.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


HA_MATERIALIZATION_POLICY: dict[str, dict[str, Any]] = {
    # HA projection is intentionally separate from canonical semantic composition.
    # topology_kind describes the primitive actually used by this release.
    "energy_site": {"ha_materialization": True, "topology_kind": "root"},
    "flexible_loads": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "grid_connection": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "grid_phase": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_production": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_inverter": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_inverter_phase": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "battery_system": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "battery": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_optimizer_site": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_zone": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_optimizer": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_panel": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "home_consumption": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "flexible_load": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "gas_meter": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "solar_forecast": {"ha_materialization": True, "topology_kind": "semantic_only"},
    "price_source": {"ha_materialization": True, "topology_kind": "semantic_only"},
}


def ha_projection_metadata(asset: dict[str, Any]) -> dict[str, Any]:
    """Return explicit HA materialisation metadata for one canonical node."""
    object_class = str(asset.get("object_class") or asset.get("asset_type") or "")
    policy = HA_MATERIALIZATION_POLICY.get(object_class)
    if policy is not None:
        return dict(policy)
    # Unknown future semantic objects fail closed: they remain in canonical truth
    # but are presentation-only until an HA projection policy is deliberately added.
    return {"ha_materialization": False, "topology_kind": "presentation_only"}


TOP_LEVEL_CANONICAL_CLASSES = {
    "grid_connection",
    "solar_production",
    "battery_system",
    "solar_optimizer_site",
    "home_consumption",
    "gas_meter",
    "solar_forecast",
    "price_source",
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
        "projection_role": "domain_root",
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
        "projection_role": "logical_group",
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
    for row in rows:
        row.update(ha_projection_metadata(row))
    for asset in assets:
        if not isinstance(asset, dict) or not asset.get("asset_id"):
            continue
        row = deepcopy(asset)
        row["parent_asset_id"] = canonical_parent_asset_id(row)
        row.update(ha_projection_metadata(row))
        rows.append(row)

    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        asset_id = str(row.get("asset_id") or "")
        if asset_id:
            dedup[asset_id] = row

    # The canonical graph, not HA via-device, is topology authority.
    children: dict[str, list[str]] = {asset_id: [] for asset_id in dedup}
    for asset_id, row in dedup.items():
        parent = str(row.get("parent_asset_id") or "")
        if parent and parent in children:
            children[parent].append(asset_id)

    def path_for(asset_id: str) -> list[str]:
        path: list[str] = []
        seen: set[str] = set()
        current = asset_id
        while current and current not in seen and current in dedup:
            seen.add(current)
            path.append(current)
            current = str(dedup[current].get("parent_asset_id") or "")
        return list(reversed(path))

    projected: list[dict[str, Any]] = []
    for asset_id in sorted(dedup):
        row = dedup[asset_id]
        path = path_for(asset_id)
        row["children"] = sorted(children.get(asset_id) or [])
        row["canonical_path"] = path
        row["canonical_depth"] = max(0, len(path) - 1)
        row["canonical_root"] = path[0] if path else asset_id
        projected.append(row)
    return projected
