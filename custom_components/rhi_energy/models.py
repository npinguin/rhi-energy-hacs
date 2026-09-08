"""Typed internal Energy model shapes.

These types deliberately cover only the domain-core records where a misspelled key can
silently break runtime projection.  Home Assistant payloads and external contracts stay
plain mappings at their boundaries.
"""
from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class SourceIdentity(TypedDict, total=False):
    source_kind: str
    integration_domain: str
    target_scope: str
    config_entry_id: str
    device_registry_id: str
    entity_registry_id: str
    current_entity_id: str
    unique_id: str


class AcceptedBinding(TypedDict):
    kind: str
    contract_version: str
    binding_id: str
    binding_owner: str
    asset_id: str
    semantic_role: str
    candidate_id: str
    raw_capability_id: str
    source_identity: SourceIdentity
    target_scope: str
    technical_capability: dict[str, Any]
    evidence: dict[str, Any]
    quality: dict[str, Any]
    semantic_binding_confidence: str
    binding_revision: int
    resolution_revision: int
    candidate_revision: NotRequired[Any]
    published_match: NotRequired[dict[str, Any]]


class LogicalProperty(TypedDict, total=False):
    property_key: str
    display_name: str
    unit: str | None
    kind: str
    input_id: str | None
    required: bool
    derived: bool
    status: str
    candidate_count: int
    issues: list[str]
    fact_key: str | None
    value: Any
    availability: str
    binding_id: str
    binding_ids: list[str]
    raw_capability_id: str
    integration_domain: str
    device_registry_id: str
    config_entry_id: str
    entity_registry_id: str
    current_entity_id: str
    unique_id: str
    target_scope: str
    platform: str


class LogicalAsset(TypedDict, total=False):
    asset_id: str
    object_class: str
    asset_type: str
    display_name: str
    builder_id: str
    integration_domain: str
    selection_mode: str
    selected_device_ids: list[str]
    normalization_status: str
    runtime_truth: bool
    parent_asset_id: str
    source_asset_id: str
    properties: list[LogicalProperty]
    health: str
    property_count: int
    available_property_count: int
    lifecycle_scope: str
    source_domain: str
    device_registry_id: str
    via_device_registry_id: str


class CompiledEnergyModel(TypedDict, total=False):
    kind: str
    contract_version: str
    domain_id: str
    concepts: dict[str, Any]
    accepted_bindings: list[AcceptedBinding]
    logical_assets: list[LogicalAsset]
    explicitly_absent_concepts: list[str]
    concept_assessments: dict[str, dict[str, Any]]
    technical_observations: dict[str, Any]
    issues: list[str]
    source_revisions: list[Any]
    normalization: dict[str, Any]
    compiled_model_revision: int


class CanonicalFact(TypedDict, total=False):
    fact_key: str
    value: Any
    availability: str
    source_asset_id: str
    integration_domain: str
    observed_at: str
    quality: str


class ProviderRuntime(TypedDict, total=False):
    asset_id: str
    builder_id: str
    integration_domain: str
    bindings: dict[str, Any]
    units: list[dict[str, Any]]
    meters: list[dict[str, Any]]
    optimizers: list[dict[str, Any]]
    normalization_status: str


class CommandRecord(TypedDict, total=False):
    operation_id: str
    idempotency_key: str
    fingerprint: str
    command_id: str
    target_asset_id: str
    period_id: str | None
    requested_at: str
    deadline_at: str
    completed_at: str
    status: str
    dispatch_state: str
    reason: str
    producer_domain: str | None
    parameters: dict[str, Any]
    expected_state: str | None
    expected_requested_power_kw: float | None
