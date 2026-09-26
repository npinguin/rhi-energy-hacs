"""Pure Energy source provenance index.

This module deliberately does not inspect or mutate Home Assistant registries.
Ordinary boot/runtime must never perform source-device topology cleanup or reconciliation.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def _model_binding_rows(model: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for binding in model.get("accepted_bindings") or []:
        if not isinstance(binding, dict):
            continue
        identity = binding.get("source_identity") or {}
        device_id = identity.get("device_registry_id") if isinstance(identity, dict) else None
        if not device_id:
            continue
        rows.append({
            "source_device_id": str(device_id),
            "logical_asset_id": str(binding.get("asset_id") or binding.get("logical_asset_id") or binding.get("concept_id") or ""),
            "binding_id": str(binding.get("binding_id") or ""),
            "source_owner": str(binding.get("integration_domain") or identity.get("integration_domain") or ""),
        })
    return rows


def _producer_binding_rows(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for collection in ("flexible_assets", "connections"):
        for item in snapshot.get(collection) or []:
            if not isinstance(item, dict):
                continue
            provenance = item.get("source_provenance") or {}
            if not isinstance(provenance, dict):
                provenance = {}
            device_id = (
                item.get("device_registry_id")
                or item.get("device_id")
                or provenance.get("device_registry_id")
                or provenance.get("device_id")
            )
            if not device_id:
                continue
            rows.append({
                "source_device_id": str(device_id),
                "logical_asset_id": str(item.get("asset_id") or item.get("connection_asset_id") or ""),
                "binding_id": str(item.get("binding_id") or provenance.get("binding_id") or ""),
                "source_owner": str(item.get("source_domain") or provenance.get("source_domain") or "mobility"),
            })
    return rows


def source_binding_index(
    model: dict[str, Any] | None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return exact source-device provenance; never infer HA topology."""
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"logical_asset_ids": set(), "binding_ids": set(), "source_owners": set()}
    )
    for row in _model_binding_rows(model or {}) + _producer_binding_rows(snapshot or {}):
        device_id = row["source_device_id"]
        if row["logical_asset_id"]:
            grouped[device_id]["logical_asset_ids"].add(row["logical_asset_id"])
        if row["binding_id"]:
            grouped[device_id]["binding_ids"].add(row["binding_id"])
        if row["source_owner"]:
            grouped[device_id]["source_owners"].add(row["source_owner"])
    return {
        device_id: {
            "source_device_id": device_id,
            "logical_asset_ids": sorted(value["logical_asset_ids"]),
            "binding_ids": sorted(value["binding_ids"]),
            "source_owners": sorted(value["source_owners"]),
        }
        for device_id, value in grouped.items()
    }


def source_device_ids(
    model: dict[str, Any] | None,
    snapshot: dict[str, Any] | None = None,
) -> set[str]:
    return set(source_binding_index(model, snapshot))
