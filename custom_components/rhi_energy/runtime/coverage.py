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
    explicit = resolution.get("producer_kind")
    if explicit:
        return str(explicit)
    provenance = resolution.get("provenance") or []
    if row.get("derived") is True:
        return "DERIVED"
    if any((item or {}).get("source_type") == "accepted_binding" for item in provenance):
        return "SOURCE"
    if any((item or {}).get("source_type") == "domain_derivation" for item in provenance):
        return "DERIVED"
    if row.get("binding_id") or row.get("binding_ids"):
        return "SOURCE"
    status = str(resolution.get("resolution_kind") or resolution.get("status") or row.get("availability") or "")
    reason = str(resolution.get("reason_code") or row.get("reason_code") or "")
    if status in {"UNSUPPORTED", "UNSUPPORTED_BY_SOURCE"} or reason in {"UNSUPPORTED_BY_SOURCE", "REQUIRED_BINDING_MISSING"}:
        return "UNSUPPORTED"
    return None


def canonical_coverage(
    objects: list[dict[str, Any]],
    configuration: dict[str, Any],
    accepted_bindings: list[dict[str, Any]] | None = None,
    semantic_paths: dict[str, Any] | None = None,
    all_objects: list[dict[str, Any]] | None = None,
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
        status = str(resolution.get("resolution_kind") or resolution.get("status") or row.get("availability") or "UNKNOWN")
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
    published_binding_ids = sorted({
        str(binding_id)
        for asset in objects
        for prop in (asset.get("properties") or [])
        if isinstance(prop, dict)
        for binding_id in (
            list(prop.get("binding_ids") or [])
            + ([prop.get("binding_id")] if prop.get("binding_id") else [])
        )
        if binding_id
    })
    product_asset_ids = {
        str(asset.get("asset_id"))
        for asset in objects
        if isinstance(asset, dict) and asset.get("asset_id")
    }
    explicit_non_product_asset_ids = {
        str(asset.get("asset_id"))
        for asset in (all_objects or [])
        if (
            isinstance(asset, dict)
            and asset.get("asset_id")
            and asset.get("product_projection") is False
        )
    }

    def _binding_asset_id(binding: dict[str, Any]) -> str:
        explicit = str(binding.get("asset_id") or "").strip()
        if explicit:
            return explicit
        binding_id = str(binding.get("binding_id") or "")
        parts = binding_id.split(":", 2)
        return parts[1] if len(parts) >= 3 and parts[0] == "energy" else ""

    known_asset_ids = {
        str(asset.get("asset_id"))
        for asset in (all_objects if all_objects is not None else objects)
        if isinstance(asset, dict) and asset.get("asset_id")
    }
    known_non_product_asset_ids = known_asset_ids - product_asset_ids
    accepted_rows = [
        binding
        for binding in (accepted_bindings or [])
        if isinstance(binding, dict) and binding.get("binding_id")
    ]
    accepted_binding_ids = sorted(str(binding["binding_id"]) for binding in accepted_rows)
    product_accepted_binding_ids = sorted({
        str(binding["binding_id"])
        for binding in accepted_rows
        if _binding_asset_id(binding) in product_asset_ids
    })
    non_product_accepted_binding_ids = sorted({
        str(binding["binding_id"])
        for binding in accepted_rows
        if _binding_asset_id(binding) in known_non_product_asset_ids
    })
    # Canonical composition may collapse one source-backed semantic asset
    # (for example grid_<id>) into a stable product asset (grid_connection).
    # Once that exact accepted binding is present on a published canonical
    # property it is not orphaned merely because the pre-composition source
    # asset id is no longer materialized as a product object.
    orphan_accepted_binding_ids = sorted({
        str(binding["binding_id"])
        for binding in accepted_rows
        if _binding_asset_id(binding) not in known_asset_ids
        and str(binding["binding_id"]) not in published_binding_ids
    })
    unpublished_product_binding_ids = sorted(
        set(product_accepted_binding_ids) - set(published_binding_ids)
    )
    semantic_path_rows = semantic_paths or {}
    semantic_conflict_fact_ids = sorted({
        str(fact_id)
        for fact_id, path in semantic_path_rows.items()
        if isinstance(path, dict) and path.get("conflicts")
    })
    semantic_unowned_fact_ids = sorted({
        str(fact_id)
        for fact_id, path in semantic_path_rows.items()
        if isinstance(path, dict) and not path.get("semantic_owner")
    })
    return {
        "contract_id": "ENERGY_CANONICAL_COVERAGE_V1",
        "property_count": len(rows),
        "producer_kinds": sorted({str(row["producer_kind"]) for row in rows if row["producer_kind"]}),
        "unowned_property_ids": sorted(unowned),
        "unclassified_property_ids": sorted(unclassified),
        "unexplained_resolution_property_ids": sorted(unexplained),
        "writable_without_readback_property_ids": sorted(write_without_readback),
        "duplicate_property_ids": duplicate_ids,
        "accepted_binding_count": len(accepted_binding_ids),
        "product_accepted_binding_count": len(product_accepted_binding_ids),
        "non_product_accepted_binding_count": len(non_product_accepted_binding_ids),
        "published_binding_count": len(published_binding_ids),
        "unpublished_accepted_binding_ids": sorted(set(unpublished_product_binding_ids) | set(orphan_accepted_binding_ids)),
        "unpublished_product_binding_ids": unpublished_product_binding_ids,
        "non_product_accepted_binding_ids": non_product_accepted_binding_ids,
        "orphan_accepted_binding_ids": orphan_accepted_binding_ids,
        "source_to_canonical_complete": not unpublished_product_binding_ids and not orphan_accepted_binding_ids,
        "coverage_semantics": "product coverage blocks only product-projected accepted bindings; non-product provenance/topology bindings remain audited but non-blocking",
        "semantic_path_count": len(semantic_path_rows),
        "semantic_conflict_fact_ids": semantic_conflict_fact_ids,
        "semantic_unowned_fact_ids": semantic_unowned_fact_ids,
        "semantic_path_complete": not semantic_conflict_fact_ids and not semantic_unowned_fact_ids,
        "complete": not (
            unowned
            or unclassified
            or unexplained
            or write_without_readback
            or duplicate_ids
            or unpublished_product_binding_ids
            or orphan_accepted_binding_ids
            or semantic_conflict_fact_ids
            or semantic_unowned_fact_ids
        ),
        "rows": rows,
    }
