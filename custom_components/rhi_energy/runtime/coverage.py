"""Canonical Energy V2 ownership and resolution coverage.

This report is product/governance evidence, not another truth source. It audits the
already-built canonical objects and configuration properties so every published field
has an explicit producer kind, resolution reason and writable readback contract.
"""
from __future__ import annotations

from typing import Any


def _producer_kind(row: dict[str, Any], *, configuration: bool = False) -> str | None:
    if configuration:
        return "CONFIGURATION"
    if row.get("write_supported") is True:
        return "CONTROL_READBACK"
    resolution = row.get("resolution") or {}
    provenance = resolution.get("provenance") or []
    if row.get("derived") is True:
        return "DERIVED"
    if any((item or {}).get("source_type") == "accepted_binding" for item in provenance):
        return "SOURCE"
    if any((item or {}).get("source_type") == "domain_derivation" for item in provenance):
        return "DERIVED"
    if row.get("binding_id") or row.get("binding_ids"):
        return "SOURCE"
    return None


def canonical_coverage(
    objects: list[dict[str, Any]],
    configuration: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def add(row: dict[str, Any], *, owner: str, configuration_property: bool = False) -> None:
        raw_property_id = str(row.get("property_id") or row.get("property_key") or row.get("key") or "")
        property_id = (
            f"logical:{owner.removeprefix('energy:object:')}:{raw_property_id}"
            if owner.startswith("energy:object:") and raw_property_id
            else raw_property_id
        )
        if not property_id:
            return
        resolution = row.get("resolution") or {}
        status = str(resolution.get("status") or row.get("availability") or "UNKNOWN")
        reason = resolution.get("reason_code") or row.get("reason_code")
        producer_kind = _producer_kind(row, configuration=configuration_property)
        editable = row.get("editable") is True or row.get("write_supported") is True
        write = row.get("write") or {}
        readback = write.get("readback_property") or row.get("readback_property")
        rows.append(
            {
                "property_id": property_id,
                "owner": owner,
                "producer_kind": producer_kind,
                "status": status,
                "reason_code": reason,
                "editable": editable,
                "readback_property": readback,
                "explicitly_classified": producer_kind is not None,
                "resolution_explained": status in {"RESOLVED", "AVAILABLE"} or bool(reason),
                "write_readback_complete": (not editable) or bool(readback),
            }
        )

    for asset in objects:
        owner = f"energy:object:{asset.get('asset_id')}"
        for prop in asset.get("properties") or []:
            if isinstance(prop, dict):
                add(prop, owner=owner)

    pricing = ((configuration.get("pricing") or {}).get("properties") or [])
    strategy = ((configuration.get("strategy") or {}).get("configured_properties") or [])
    for prop in pricing:
        if isinstance(prop, dict):
            add(prop, owner="energy:configuration:pricing", configuration_property=True)
    for prop in strategy:
        if isinstance(prop, dict):
            add(prop, owner="energy:configuration:strategy", configuration_property=True)

    unowned = [row["property_id"] for row in rows if not row["owner"]]
    unclassified = [row["property_id"] for row in rows if not row["explicitly_classified"]]
    unexplained = [row["property_id"] for row in rows if not row["resolution_explained"]]
    write_without_readback = [
        row["property_id"] for row in rows if not row["write_readback_complete"]
    ]
    duplicate_ids = sorted(
        {
            row["property_id"]
            for row in rows
            if sum(other["property_id"] == row["property_id"] for other in rows) > 1
        }
    )
    return {
        "contract_id": "ENERGY_CANONICAL_COVERAGE_V1",
        "property_count": len(rows),
        "producer_kinds": sorted({str(row["producer_kind"]) for row in rows if row["producer_kind"]}),
        "unowned_property_ids": sorted(unowned),
        "unclassified_property_ids": sorted(unclassified),
        "unexplained_resolution_property_ids": sorted(unexplained),
        "writable_without_readback_property_ids": sorted(write_without_readback),
        "duplicate_property_ids": duplicate_ids,
        "complete": not (unowned or unclassified or unexplained or write_without_readback or duplicate_ids),
        "rows": rows,
    }
