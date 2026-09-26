"""Typed property resolution for the Energy V2 public contract.

Compilation answers whether a source is semantically safe. Runtime resolution answers
whether that fixed source produced usable evidence now. The two decisions deliberately
remain separate: runtime never discovers, re-matches or silently substitutes a source.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from ..models import PropertyProducerKind, PropertyResolution, PropertyResolutionKind
except ImportError:  # direct runpy tests
    PropertyResolution = dict  # type: ignore[assignment,misc]
    class PropertyProducerKind:
        SOURCE="SOURCE"; DERIVED="DERIVED"; CONTROL_READBACK="CONTROL_READBACK"
    class PropertyResolutionKind:
        AVAILABLE="AVAILABLE"; UNSUPPORTED_BY_SOURCE="UNSUPPORTED_BY_SOURCE"; UNAVAILABLE_TEMPORARY="UNAVAILABLE_TEMPORARY"


def _binding_ids(prop: dict[str, Any]) -> list[str]:
    values = prop.get("binding_ids") or []
    if prop.get("binding_id") and not values:
        values = [prop["binding_id"]]
    return sorted({str(value) for value in values if value})


def _provenance(prop: dict[str, Any], binding_ids: list[str]) -> list[dict[str, Any]]:
    if not binding_ids:
        if prop.get("derived"):
            return [{"source_type": "domain_derivation"}]
        if str(prop.get("producer_kind") or "").upper() == "SOURCE":
            return [{
                "source_type": "producer_contract",
                **({"source_domain": str(prop.get("source_domain"))} if prop.get("source_domain") else {}),
            }]
        return []
    source = {
        key: deepcopy(prop.get(key))
        for key in (
            "integration_domain",
            "config_entry_id",
            "device_registry_id",
            "entity_registry_id",
            "current_entity_id",
            "unique_id",
            "raw_capability_id",
        )
        if prop.get(key) not in {None, ""}
    }
    return [{"binding_id": binding_id, "source_type": "accepted_binding", **source} for binding_id in binding_ids]


def resolve_property(prop: dict[str, Any], value: Any, *, value_revision: int = 1) -> PropertyResolution:
    """Resolve one fixed logical property without source selection or guessing."""
    binding_ids = _binding_ids(prop)
    provenance = _provenance(prop, binding_ids)
    acceptance_status = str(prop.get("status") or "")
    explicit_producer_kind = str(prop.get("producer_kind") or "").upper()
    producer_kind = (
        explicit_producer_kind
        if explicit_producer_kind in {"SOURCE", "DERIVED", "CONTROL_READBACK", "CONFIGURATION"}
        else PropertyProducerKind.CONTROL_READBACK
        if prop.get("write_supported") is True
        else PropertyProducerKind.DERIVED
        if prop.get("derived") is True
        else PropertyProducerKind.SOURCE
        if binding_ids
        else None
    )

    if acceptance_status in {"MISSING", "UNSUPPORTED"}:
        return {
            "status": "UNRESOLVED",
            "quality": "NOT_ASSESSED",
            "reason_code": "REQUIRED_BINDING_MISSING" if prop.get("required") else "CAPABILITY_UNSUPPORTED",
            "binding_ids": binding_ids,
            "provenance": provenance,
            "value_revision": value_revision,
            "producer_kind": None if producer_kind is None else str(producer_kind),
            "resolution_kind": str(PropertyResolutionKind.UNSUPPORTED_BY_SOURCE),
        }
    if value is None:
        return {
            "status": "UNAVAILABLE",
            "quality": "NOT_ASSESSED",
            "reason_code": "DERIVATION_INPUTS_INCOMPLETE" if prop.get("derived") else "SOURCE_STATE_UNAVAILABLE",
            "binding_ids": binding_ids,
            "provenance": provenance,
            "value_revision": value_revision,
            "producer_kind": None if producer_kind is None else str(producer_kind),
            "resolution_kind": str(PropertyResolutionKind.UNAVAILABLE_TEMPORARY),
        }
    return {
        "status": "RESOLVED",
        "quality": "DERIVED" if prop.get("derived") else "AUTHORITATIVE",
        "reason_code": "DOMAIN_DERIVATION" if prop.get("derived") else "ACCEPTED_BINDING_VALUE",
        "binding_ids": binding_ids,
        "provenance": provenance,
        "value_revision": value_revision,
        "producer_kind": None if producer_kind is None else str(producer_kind),
        "resolution_kind": str(PropertyResolutionKind.AVAILABLE),
    }


def compatibility_availability(resolution: PropertyResolution) -> str:
    """Map the canonical V2 decision to the legacy availability vocabulary."""
    status = resolution["status"]
    if status == "RESOLVED":
        return "AVAILABLE"
    if status == "UNRESOLVED" and resolution["reason_code"] == "REQUIRED_BINDING_MISSING":
        return "INCOMPLETE"
    return "UNAVAILABLE"
