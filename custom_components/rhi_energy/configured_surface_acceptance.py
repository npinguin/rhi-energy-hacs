"""Energy-local acceptance adapter for Foundation configured surface inputs."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

SURFACE_CONTRACT_VERSION = "1.0.0"
_ALLOWED_OBJECTS = {
    "grid_connection": "grid_connection",
    "solar_source": "solar_production",
    "battery": "battery_system",
}


def surface_assessment_key(row: dict[str, Any]) -> str:
    return (
        f"configured_surface:{row.get('concept_id') or 'unknown'}:"
        f"{row.get('instance_id') or 'unknown'}"
    )


def adapt_configured_surface_input(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Convert explicit user mappings to Energy's existing semantic-input shape.

    This is an Energy-local adapter, not a Foundation builder. The configured field_id
    is already a canonical Energy normalized input id and therefore needs no mapping table.
    """
    if row.get("kind") != "configured_domain_surface_input":
        raise ValueError("configured_surface_kind_invalid")
    if row.get("contract_version") != SURFACE_CONTRACT_VERSION:
        raise ValueError("configured_surface_contract_unsupported")
    if row.get("domain_id") != "energy":
        raise ValueError("configured_surface_domain_invalid")

    object_type = str(row.get("object_type") or "")
    concept_id = str(row.get("concept_id") or "")
    expected_concept = _ALLOWED_OBJECTS.get(object_type)
    if expected_concept is None or expected_concept != concept_id:
        raise ValueError("configured_surface_object_concept_invalid")

    discovery = row.get("discovery_assessment") or {}
    if discovery.get("required_inputs_complete") is not True:
        raise ValueError("configured_surface_incomplete")
    if discovery.get("review_required") is True:
        raise ValueError("configured_surface_review_required")

    groups: list[dict[str, Any]] = []
    integrations: set[str] = set()
    for field in row.get("fields") or []:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or "")
        source = deepcopy(field.get("source_identity") or {})
        if not field_id or not source.get("entity_registry_id") or not source.get("target_scope"):
            raise ValueError(f"configured_surface_field_invalid:{field_id or 'missing'}")
        integration = str(source.get("integration_domain") or "")
        if integration:
            integrations.add(integration)
        candidate = {
            "candidate_id": str(field.get("candidate_id") or f"configured:{field_id}"),
            "candidate_revision": int(row.get("candidate_revision") or 1),
            "source_identity": source,
            "technical_capability": deepcopy(field.get("technical_capability") or {}),
            "evidence": {
                "provenance": ["explicit_foundation_configuration_surface"],
                "device_registry_id": source.get("device_registry_id"),
            },
            "quality": deepcopy(field.get("quality") or {}),
            "configured_surface_field_id": field_id,
        }
        groups.append({
            "input_id": field_id,
            "required": False,
            "cardinality": "zero_or_one",
            "technical_capabilities": [
                str((candidate["technical_capability"] or {}).get("capability_class") or "")
            ],
            "allowed_source_kinds": [str(source.get("source_kind") or "entity")],
            "candidate_ids": [candidate["candidate_id"]],
            "candidate_count": 1,
            "candidates": [candidate],
            "candidate_matches": [],
        })

    if not groups:
        raise ValueError("configured_surface_no_fields")
    integration_domain = next(iter(integrations)) if len(integrations) == 1 else "configured_entities"
    key = surface_assessment_key(row)
    adapted = {
        "kind": "energy_configured_surface_semantic_input",
        "contract_version": "1.0.0",
        "builder_id": key,
        "configured_surface": True,
        "configured_object_type": object_type,
        "surface_id": row.get("surface_id"),
        "instance_id": row.get("instance_id"),
        "configuration_revision": int(row.get("configuration_revision") or 1),
        "candidate_revision": int(row.get("candidate_revision") or 1),
        "build_input_revision": int(row.get("build_input_revision") or 1),
        "selection": {
            "concept": concept_id,
            "integration_domain": integration_domain,
            "device_filter_mode": "explicit_entities",
            "selected_device_ids": sorted({
                str((field.get("source_identity") or {}).get("device_registry_id"))
                for field in row.get("fields") or []
                if (field.get("source_identity") or {}).get("device_registry_id")
            }),
        },
        "candidate_groups": groups,
        "candidate_evidence": [
            deepcopy(group["candidates"][0]) for group in groups
        ],
        "discovery_assessment": deepcopy(discovery),
    }
    return key, adapted
