"""Canonical Energy public contract V2 and the V1 compatibility boundary."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

try:
    from .const import RELEASE
except ImportError:  # direct runpy tests
    from pathlib import Path as _Path
    import runpy as _runpy

    RELEASE = _runpy.run_path(str(_Path(__file__).resolve().parent / "const.py"))["RELEASE"]

PUBLIC_CONTRACT_V2 = "2.0.0"

PUBLIC_PROFILE_CONTRACT = "ENERGY_ASSET_PROFILE_V2"


def _profile_id(asset: dict[str, Any]) -> str:
    """Return one stable domain profile id from already-normalized Energy identity.

    Profiles classify Energy device types and integration families. They are not
    commercial SKU identity and never derive semantics from display names or artwork.
    """
    asset_type = str(asset.get("asset_type") or asset.get("object_class") or "unknown").strip().lower()
    integration = str(asset.get("integration_domain") or asset.get("source_domain") or "energy").strip().lower()
    safe_type = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in asset_type)
    safe_integration = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in integration)
    return f"energy.{safe_type}.{safe_integration}"


def _publication(asset: dict[str, Any]) -> dict[str, Any]:
    props = [row for row in asset.get("properties") or [] if isinstance(row, dict)]
    published = sorted({str(row.get("property_key")) for row in props if row.get("property_key")})
    required = sorted({
        str(row.get("property_key"))
        for row in props
        if row.get("property_key") and row.get("required") is True
    })
    resolved = sorted({
        str(row.get("property_key"))
        for row in props
        if row.get("property_key") and (row.get("resolution") or {}).get("status") == "RESOLVED"
    })
    missing_required = sorted(set(required) - set(published))
    unresolved_required = sorted(set(required) - set(resolved))
    return {
        "authority": "RHI_ENERGY_PUBLIC_CONTRACT_V2",
        "expected_property_keys": published,
        "published_property_keys": published,
        "required_property_keys": required,
        "missing_required_property_keys": missing_required,
        "resolved_property_keys": resolved,
        "unresolved_required_property_keys": unresolved_required,
        "complete": not missing_required,
        "resolution_complete": not unresolved_required,
        "v1_fallback_allowed": False,
    }


def _decorate_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for raw in objects:
        if not isinstance(raw, dict):
            continue
        asset = deepcopy(raw)
        asset_type = str(asset.get("asset_type") or asset.get("object_class") or "").strip()
        if asset_type:
            asset["asset_type"] = asset_type
        asset["profile_id"] = _profile_id(asset)
        asset["property_publication"] = _publication(asset)
        decorated.append(asset)
    return decorated


def _profile_catalog(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a small read-only catalog from canonical Energy asset metadata."""
    profiles: dict[str, dict[str, Any]] = {}
    for asset in objects:
        profile_id = str(asset.get("profile_id") or _profile_id(asset))
        row = profiles.setdefault(
            profile_id,
            {
                "contract_id": PUBLIC_PROFILE_CONTRACT,
                "profile_id": profile_id,
                "asset_type": str(asset.get("asset_type") or asset.get("object_class") or ""),
                "profile_scope": "domain_asset_type",
                "source_domain": str(asset.get("source_domain") or "energy"),
                "integration_domain": str(asset.get("integration_domain") or ""),
                "builder_ids": [],
                "property_keys": [],
                "required_property_keys": [],
                "editable": False,
            },
        )
        builder_id = str(asset.get("builder_id") or "")
        if builder_id and builder_id not in row["builder_ids"]:
            row["builder_ids"].append(builder_id)
        publication = asset.get("property_publication") or {}
        row["property_keys"] = sorted(set(row["property_keys"]) | set(publication.get("expected_property_keys") or []))
        row["required_property_keys"] = sorted(
            set(row["required_property_keys"]) | set(publication.get("required_property_keys") or [])
        )
    return [profiles[key] for key in sorted(profiles)]


def _relationships(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for asset in snapshot.get("logical_assets") or []:
        source = str(asset.get("parent_asset_id") or "")
        target = str(asset.get("asset_id") or "")
        if source and target:
            relationship_id = f"energy:{source}:contains:{target}"
            rows[relationship_id] = {
                "relationship_id": relationship_id,
                "source_asset_id": source,
                "target_asset_id": target,
                "relationship_type": "contains",
                "source_domain": "energy",
            }
    logical_assets = [item for item in snapshot.get("logical_assets") or [] if isinstance(item, dict)]
    home_asset = next((item for item in logical_assets if item.get("object_class") == "home_consumption"), None)
    home_id = str((home_asset or {}).get("asset_id") or "home_consumption")
    for asset in logical_assets:
        aid = str(asset.get("asset_id") or "")
        object_class = str(asset.get("object_class") or "")
        if not aid:
            continue
        relation_type = None
        source, target = aid, home_id
        flow_role = None
        if object_class == "solar_inverter":
            relation_type, flow_role = "supplies", "solar_supply"
        elif object_class == "battery":
            relation_type, flow_role = "exchanges_with", "stationary_battery"
        elif object_class == "grid_connection":
            relation_type, flow_role = "exchanges_with", "grid_boundary"
        elif object_class == "flexible_load":
            relation_type, flow_role = "supplies", "flexible_demand"
            source, target = home_id, aid
        if relation_type:
            relationship_id = f"energy:physical:{source}:{relation_type}:{target}"
            rows[relationship_id] = {
                "relationship_id": relationship_id,
                "source_asset_id": source,
                "target_asset_id": target,
                "relationship_type": relation_type,
                "source_domain": "energy",
                "physical": True,
                "flow_role": flow_role,
            }
    for index, relation in enumerate(snapshot.get("connections") or []):
        if not isinstance(relation, dict):
            continue
        source = relation.get("source_asset_id") or relation.get("from_asset_id") or relation.get("source")
        target = relation.get("target_asset_id") or relation.get("to_asset_id") or relation.get("target")
        if not source or not target:
            continue
        relationship_id = str(relation.get("relationship_id") or f"external:{index}:{source}:{target}")
        rows[relationship_id] = {
            "relationship_id": relationship_id,
            "source_asset_id": str(source),
            "target_asset_id": str(target),
            "relationship_type": str(relation.get("relationship_type") or relation.get("type") or "connected_to"),
            "source_domain": str(relation.get("source_domain") or "external"),
        }
    return [rows[key] for key in sorted(rows)]


def build_public_contract_v2(
    snapshot: dict[str, Any],
    store_data: dict[str, Any],
    command_rows: list[dict[str, Any]],
    model: dict[str, Any],
) -> dict[str, Any]:
    """Build one object-centric contract from resolved runtime truth.

    ``_compatibility`` is an internal lossless envelope used only by the V1 facade.
    It is stripped from the published V2 payload and prevents the facade from reading
    mutable runtime state through a second path.
    """
    source = deepcopy(snapshot)
    source["settings"] = deepcopy(store_data.get("settings") or {})
    concepts = model.get("concepts") or {}
    source["battery_reserve_write_supported"] = bool(
        (concepts.get("battery_system") or {}).get("reserve_binding")
    )
    objects = _decorate_objects(deepcopy(source.get("logical_assets") or []))
    unresolved = sum(
        1
        for asset in objects
        for prop in asset.get("properties") or []
        if (prop.get("resolution") or {}).get("status") != "RESOLVED"
    )
    return {
        "kind": "rhi_energy_public_contract",
        "contract_version": PUBLIC_CONTRACT_V2,
        "domain_id": "energy",
        "release": RELEASE,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain_model_revision": model.get("domain_model_revision"),
        "generation": deepcopy(model.get("generation") or {}),
        "layers": {
            "contract_version": model.get("layer_contract_version"),
            "model_fingerprint": model.get("model_fingerprint"),
            "health": deepcopy(source.get("layer_health") or model.get("layer_health") or {}),
            "system_objects": deepcopy(source.get("system_assets") or model.get("system_assets") or []),
            "planning_objects": deepcopy(source.get("planning_assets") or model.get("planning_assets") or []),
            "intelligence_objects": deepcopy(source.get("intelligence_assets") or model.get("intelligence_assets") or []),
            "dependency_diagnostics": deepcopy(model.get("dependency_diagnostics") or {}),
        },
        "health": source.get("health") or "UNKNOWN",
        "objects": objects,
        "profiles": _profile_catalog(objects),
        "relationships": _relationships(source),
        "planning": deepcopy(source.get("plan") or {}),
        "intelligence": deepcopy(source.get("intelligence") or {}),
        "overview": deepcopy(source.get("overview") or {}),
        "commands": deepcopy(command_rows),
        "summary": {
            "object_count": len(objects),
            "profile_count": len(_profile_catalog(objects)),
            "property_count": sum(len(asset.get("properties") or []) for asset in objects),
            "unresolved_property_count": unresolved,
            "relationship_count": len(_relationships(source)),
            "system_object_count": len(source.get("system_assets") or model.get("system_assets") or []),
            "planning_object_count": len(source.get("planning_assets") or model.get("planning_assets") or []),
            "intelligence_object_count": len(source.get("intelligence_assets") or model.get("intelligence_assets") or []),
            "dependency_edge_count": len(model.get("dependencies") or []),
        },
        "_compatibility": source,
    }


def published_v2(contract: dict[str, Any]) -> dict[str, Any]:
    """Return the public payload without the private V1 reconstruction envelope."""
    return {key: deepcopy(value) for key, value in contract.items() if key != "_compatibility"}


def compatibility_snapshot(contract: dict[str, Any]) -> dict[str, Any]:
    """Return the exact V1 source snapshot carried by one immutable V2 decision."""
    if contract.get("kind") != "rhi_energy_public_contract" or contract.get("contract_version") != PUBLIC_CONTRACT_V2:
        raise ValueError("unsupported_energy_public_contract")
    source = contract.get("_compatibility")
    if not isinstance(source, dict):
        raise ValueError("energy_v2_compatibility_envelope_missing")
    return deepcopy(source)
