"""Bounded logical topology descriptors for solar optimizer hierarchy."""
from __future__ import annotations

from typing import Any


def optimizer_descriptors(provider: dict[str, Any]) -> list[dict[str, Any]]:
    """Return evidence-backed site/zone/optimizer descriptors.

    Exact HA source-device parent evidence is translated to canonical composition only
    when both endpoints are accepted optimizer objects. Display names are never used
    to infer topology. When an optimizer-to-zone edge is not proven, the governed
    fallback remains the single accepted optimizer site.
    """
    sites = [row for row in provider.get("sites") or [] if isinstance(row, dict)]
    zones = [row for row in provider.get("zones") or [] if isinstance(row, dict)]
    optimizers = [row for row in provider.get("optimizers") or [] if isinstance(row, dict)]

    site_parent = str(sites[0].get("asset_id") or "") if len(sites) == 1 else None
    device_to_asset = {
        str(row.get("device_registry_id")): str(row.get("asset_id"))
        for row in (*sites, *zones, *optimizers)
        if row.get("device_registry_id") and row.get("asset_id")
    }
    asset_class = {
        str(row.get("asset_id")): object_class
        for collection, object_class in (
            (sites, "solar_optimizer_site"),
            (zones, "solar_zone"),
            (optimizers, "solar_optimizer"),
        )
        for row in collection
        if row.get("asset_id")
    }

    def parent_for(row: dict[str, Any], object_class: str) -> str | None:
        source_parent_device = str(row.get("via_device_registry_id") or "")
        exact_parent = device_to_asset.get(source_parent_device)
        exact_parent_class = asset_class.get(exact_parent or "")
        if object_class == "solar_zone":
            if exact_parent_class == "solar_optimizer_site":
                return exact_parent
            return site_parent
        if object_class == "solar_optimizer":
            if exact_parent_class in {"solar_zone", "solar_optimizer_site"}:
                return exact_parent
            return site_parent
        return None

    rows: list[dict[str, Any]] = []
    for collection, object_class, label in (
        (sites, "solar_optimizer_site", "Solar Optimizer Site"),
        (zones, "solar_zone", "Solar Zone / String"),
        (optimizers, "solar_optimizer", "Solar Optimizer"),
    ):
        for raw in collection:
            if not isinstance(raw, dict) or not raw.get("asset_id"):
                continue
            rows.append({
                "row": raw,
                "object_class": object_class,
                "display_name": str(raw.get("display_name") or label),
                "parent_asset_id": parent_for(raw, object_class),
                "topology_evidence": (
                    "exact_source_via_device"
                    if str(raw.get("via_device_registry_id") or "") in device_to_asset
                    else "single_site_fallback"
                    if object_class != "solar_optimizer_site" and site_parent
                    else "none"
                ),
                "panel_binding": (
                    (raw.get("bindings") or {}).get("panel_identity")
                    if object_class == "solar_optimizer"
                    else None
                ),
            })
    return rows
