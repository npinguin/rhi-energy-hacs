"""Bounded logical topology descriptors for SolarEdge Optimizer hierarchy."""
from __future__ import annotations

from typing import Any


def optimizer_descriptors(provider: dict[str, Any]) -> list[dict[str, Any]]:
    """Return evidence-backed site/zone/optimizer descriptors without inventing zone membership."""
    sites = [row for row in provider.get("sites") or [] if isinstance(row, dict)]
    site_parent = str(sites[0].get("asset_id") or "") if len(sites) == 1 else None
    rows: list[dict[str, Any]] = []
    for collection, object_class, label in (
        (sites, "solar_optimizer_site", "Solar Optimizer Site"),
        (provider.get("zones") or [], "solar_zone", "Solar Zone"),
        (provider.get("optimizers") or [], "solar_optimizer", "Solar Optimizer"),
    ):
        for raw in collection:
            if not isinstance(raw, dict) or not raw.get("asset_id"):
                continue
            rows.append({
                "row": raw,
                "object_class": object_class,
                "display_name": str(raw.get("display_name") or label),
                "parent_asset_id": site_parent if object_class != "solar_optimizer_site" else None,
                "panel_binding": (
                    (raw.get("bindings") or {}).get("panel_identity")
                    if object_class == "solar_optimizer"
                    else None
                ),
            })
    return rows
