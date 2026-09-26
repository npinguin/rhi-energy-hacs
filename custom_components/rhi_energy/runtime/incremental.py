"""Incremental high-cardinality telemetry updates.

This module is deliberately separate from the domain recompute engine. It updates
already-materialized leaf properties only and cannot own topology or entity lifecycle.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .resolution import compatibility_availability, resolve_property

_ALLOWED_OPTIMIZER_CLASSES = {
    "solar_optimizer_site",
    "solar_zone",
    "solar_optimizer",
    "solar_panel",
}


def build_entity_targets(model: dict[str, Any] | None) -> dict[str, tuple[tuple[str, str], ...]]:
    """Build entity -> logical property targets once per structural model activation."""
    if model is None:
        return {}
    binding_entities = {
        str(row.get("binding_id")): str(
            (row.get("source_identity") or {}).get("current_entity_id") or ""
        )
        for row in (model.get("accepted_bindings") or [])
        if isinstance(row, dict) and row.get("binding_id")
    }
    targets: dict[str, list[tuple[str, str]]] = {}
    for asset in model.get("logical_assets") or []:
        if not isinstance(asset, dict) or not asset.get("asset_id"):
            continue
        asset_id = str(asset["asset_id"])
        for prop in asset.get("properties") or []:
            if not isinstance(prop, dict) or not prop.get("property_key"):
                continue
            binding_ids = [str(value) for value in (prop.get("binding_ids") or []) if value]
            if prop.get("binding_id"):
                binding_ids.append(str(prop["binding_id"]))
            for entity_id in {binding_entities.get(binding_id, "") for binding_id in binding_ids}:
                if entity_id:
                    targets.setdefault(entity_id, []).append(
                        (asset_id, str(prop["property_key"]))
                    )
    return {
        entity_id: tuple(sorted(set(rows)))
        for entity_id, rows in targets.items()
    }


def update_optimizer_entity(runtime, entity_id: str) -> bool:
    """Update one optimizer/panel source event without a domain-wide recompute."""
    targets = runtime._incremental_entity_targets.get(entity_id) or ()
    if not targets or runtime.model is None:
        return False

    assets = {
        str(row.get("asset_id")): row
        for row in (runtime.snapshot.get("logical_assets") or [])
        if isinstance(row, dict) and row.get("asset_id")
    }
    target_assets = [assets.get(asset_id) for asset_id, _property_key in targets]
    if not target_assets or any(
        asset is None
        or str(asset.get("integration_domain") or "") != "solaredgeoptimizers"
        or str(asset.get("object_class") or "") not in _ALLOWED_OPTIMIZER_CLASSES
        for asset in target_assets
    ):
        return False

    facts = runtime.snapshot.setdefault("facts", {})
    touched_assets: set[str] = set()
    for asset_id, property_key in targets:
        asset = assets.get(asset_id)
        if asset is None:
            continue
        prop = next(
            (
                row
                for row in (asset.get("properties") or [])
                if isinstance(row, dict)
                and str(row.get("property_key") or "") == property_key
            ),
            None,
        )
        if prop is None:
            continue

        value = runtime._read_property(asset, prop, facts)
        if prop.get("fact_key"):
            facts[str(prop["fact_key"])] = value
        prop["value"] = value
        resolution = resolve_property(
            prop,
            value,
            value_revision=int(asset.get("value_revision") or 1),
        )
        prop["resolution"] = resolution
        prop["availability"] = compatibility_availability(resolution)
        if resolution["status"] == "RESOLVED" and asset.get("runtime_truth"):
            prop["status"] = "NORMALIZED"
        touched_assets.add(asset_id)

    for asset_id in touched_assets:
        asset = assets[asset_id]
        available = sum(
            1
            for prop in (asset.get("properties") or [])
            if isinstance(prop, dict)
            and ((prop.get("resolution") or {}).get("status") == "RESOLVED")
        )
        missing_required = sum(
            1
            for prop in (asset.get("properties") or [])
            if isinstance(prop, dict)
            and prop.get("required")
            and ((prop.get("resolution") or {}).get("status") != "RESOLVED")
        )
        asset["available_property_count"] = available
        if asset.get("runtime_truth"):
            asset["health"] = "DEGRADED" if missing_required or not available else "OK"

    runtime.snapshot["snapshot_revision"] = int(
        runtime.snapshot.get("snapshot_revision") or 0
    ) + 1
    runtime.snapshot["observed_at"] = datetime.now(UTC).isoformat()
    runtime._notify()
    return True
