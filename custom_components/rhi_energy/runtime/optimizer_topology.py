"""Bounded logical topology descriptors for solar optimizer hierarchy."""
from __future__ import annotations

from typing import Any

try:
    from ..adapters import get_topology_key_resolver
except ImportError:  # direct runpy tests without package context
    from pathlib import Path as _Path
    import runpy as _runpy

    _root = _Path(__file__).resolve().parents[1]

    def get_topology_key_resolver(integration_domain):
        domain = str(integration_domain or "").strip().lower()
        path = _root / "adapters" / f"{domain}.py"
        if not domain or not path.is_file():
            return lambda _row: None
        return _runpy.run_path(str(path)).get("topology_key", lambda _row: None)


def optimizer_descriptors(
    provider: dict[str, Any],
    *,
    master_parent_asset_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return evidence-backed site/zone/optimizer descriptors.

    Provider-owned stable topology paths are authoritative inside the optimizer
    subtree. When a local SolarEdge production master is present, the cloud site
    is attached below that master production aggregate. No display-name matching,
    registry scan, polling or telemetry-driven topology rebuild is allowed here.
    """
    sites = [row for row in provider.get("sites") or [] if isinstance(row, dict)]
    zones = [row for row in provider.get("zones") or [] if isinstance(row, dict)]
    optimizers = [row for row in provider.get("optimizers") or [] if isinstance(row, dict)]

    site_parent = str(sites[0].get("asset_id") or "") if len(sites) == 1 else None
    topology_key = get_topology_key_resolver(provider.get("integration_domain"))
    zone_keys = {
        str(key): str(row.get("asset_id"))
        for row in zones
        if row.get("asset_id") and (key := topology_key(row))
    }
    master_inverter_by_zone = {
        str(row.get("asset_id")): str(row.get("master_inverter_asset_id"))
        for row in zones
        if row.get("asset_id") and row.get("master_inverter_asset_id")
    }
    top_level_zone_ids = {
        str(row.get("asset_id"))
        for row in zones
        if row.get("asset_id") and (key := topology_key(row)) and "_" not in str(key)
    }
    suppress_site = bool(
        master_parent_asset_id
        and top_level_zone_ids
        and top_level_zone_ids.issubset(set(master_inverter_by_zone))
    )

    def topology_parent_for_key(child_key: str | None) -> str | None:
        if not child_key:
            return None
        matches = [
            (zone_key, zone_asset_id)
            for zone_key, zone_asset_id in zone_keys.items()
            if zone_key != child_key and child_key.startswith(f"{zone_key}_")
        ]
        return max(matches, key=lambda item: len(item[0]))[1] if matches else None

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
        row_key = topology_key(row)

        if object_class == "solar_optimizer_site":
            return master_parent_asset_id if not suppress_site else None

        if object_class == "solar_zone":
            if str(row.get("asset_id") or "") in master_inverter_by_zone:
                return master_inverter_by_zone[str(row.get("asset_id"))]
            stable_parent = topology_parent_for_key(row_key)
            if stable_parent:
                return master_inverter_by_zone.get(stable_parent, stable_parent)
            if exact_parent_class == "solar_optimizer_site":
                return exact_parent
            return site_parent

        if object_class == "solar_optimizer":
            if exact_parent_class == "solar_zone":
                return exact_parent
            stable_parent = topology_parent_for_key(row_key)
            if stable_parent:
                return stable_parent
            if exact_parent_class == "solar_optimizer_site":
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
            row_key = topology_key(raw)
            stable_parent = topology_parent_for_key(row_key)
            source_parent_device = str(raw.get("via_device_registry_id") or "")
            exact_parent = device_to_asset.get(source_parent_device)
            exact_parent_class = asset_class.get(exact_parent or "")
            if object_class == "solar_optimizer_site" and master_parent_asset_id:
                evidence = "master_solar_production"
            elif exact_parent_class == "solar_zone":
                evidence = "exact_source_via_device"
            elif stable_parent:
                evidence = "integration_stable_path"
            elif exact_parent_class == "solar_optimizer_site":
                evidence = "exact_source_via_device"
            elif object_class != "solar_optimizer_site" and site_parent:
                evidence = "single_site_fallback"
            else:
                evidence = "none"

            suppress_projection = bool(
                (object_class == "solar_optimizer_site" and suppress_site)
                or (
                    object_class == "solar_zone"
                    and str(raw.get("asset_id") or "") in master_inverter_by_zone
                )
            )
            rows.append({
                "row": raw,
                "object_class": object_class,
                "display_name": str(raw.get("display_name") or label),
                "parent_asset_id": parent_for(raw, object_class),
                "topology_evidence": evidence,
                "suppress_projection": suppress_projection,
                "master_inverter_asset_id": master_inverter_by_zone.get(str(raw.get("asset_id") or "")),
                "topology_key": row_key,
                "panel_binding": (
                    (raw.get("bindings") or {}).get("panel_identity")
                    if object_class == "solar_optimizer"
                    else None
                ),
            })
    return rows
