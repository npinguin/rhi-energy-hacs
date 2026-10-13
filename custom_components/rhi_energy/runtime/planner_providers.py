"""Versioned, domain-owned registry of energy planners and their truthful capabilities.

Provider configuration is not the same thing as an executable adapter. Native
HA source identity, result acceptance and single physical command ownership
remain Energy/Mobility responsibilities, never solver responsibilities.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

CONTRACT = "RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1"
PLANNING_CONTEXT_CONTRACT = "RHI_ENERGY_PLANNING_CONTEXT_V1"

class PlannerMode(StrEnum):
    PRIMARY = "primary"
    SHADOW = "shadow"
    SELECTABLE = "selectable"


@dataclass(frozen=True, slots=True)
class PlannerProvider:
    """One catalog owns both historic mode metadata and new adapter semantics."""
    provider_id: str
    label: str
    adapter: str
    contract_status: str
    configuration_kind: str
    execution_qualified: bool
    reason: str | None = None
    built_in: bool = False
    mode: PlannerMode = PlannerMode.SHADOW
    requires_service: bool = True
    can_issue_commands: bool = False

PROVIDERS = (
    PlannerProvider("rhi_deterministic", "RHI Deterministic", "canonical_energy", "SUPPORTED", "none", True, built_in=True, mode=PlannerMode.PRIMARY, requires_service=False),
    PlannerProvider("emhass", "EMHASS", "emhass_native_0_18_5", "ADVISORY_ONLY", "http_endpoint", False, "target_ha_execution_contract_not_verified", mode=PlannerMode.SELECTABLE),
    PlannerProvider("haeo", "HAEO (Home Assistant Energy Optimizer)", "haeo_ha_network", "DESIGN_ONLY", "ha_config_entry", False, "no_verified_external_context_injection_api"),
    PlannerProvider("akkudoktor_eos", "Akkudoktor EOS", "eos_versioned_http", "DESIGN_ONLY", "versioned_http", False, "versioned_optimizer_payload_not_yet_mapped"),
)

RHI_DETERMINISTIC = PROVIDERS[0]
EMHASS = PROVIDERS[1]


def available_planner_providers(*, emhass_validated: bool = False) -> tuple[PlannerProvider, ...]:
    """Backward-compatible validated execution discovery from this same catalog."""
    return (RHI_DETERMINISTIC, EMHASS) if emhass_validated else (RHI_DETERMINISTIC,)


def provider_catalog() -> dict[str, PlannerProvider]:
    return {provider.provider_id: provider for provider in PROVIDERS}

def validate_provider_id(provider_id: str) -> str:
    if not isinstance(provider_id, str) or provider_id not in provider_catalog():
        raise ValueError("unknown_planner_provider")
    return provider_id

def validate_primary_provider_id(provider_id: str) -> str:
    """Admit only providers qualified for operational plan selection.

    Connection configuration, shadow evaluation and historic user intent do not
    grant an external optimizer physical planning authority. The provider
    catalog is the one existing source of qualification truth.
    """
    selected = validate_provider_id(provider_id)
    if not provider_catalog()[selected].execution_qualified:
        raise ValueError("planner_primary_not_qualified:" + selected)
    return selected


def validate_planner_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("planner_endpoint_required")
    candidate = value.strip().rstrip("/")
    parsed = urlsplit(candidate)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.fragment or parsed.query or (parsed.path not in ("", "/"))):
        raise ValueError("planner_endpoint_invalid")
    try:
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("planner_endpoint_invalid")
    except ValueError as exc:
        raise ValueError("planner_endpoint_invalid") from exc
    return candidate

def configured_planners(options: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = options.get("planner_connections") or {}
    if not isinstance(raw, dict):
        raise ValueError("planner_connections_invalid")
    result: dict[str, dict[str, Any]] = {"rhi_deterministic": {}}
    for provider_id in ("emhass", "haeo", "akkudoktor_eos"):
        row = raw.get(provider_id)
        if row is None and provider_id == "emhass":
            old = options.get("emhass_url")
            if old:
                row = {"url": old, "timeout_seconds": options.get("emhass_timeout_seconds", 30)}
        if row is None:
            continue
        if not isinstance(row, dict):
            raise ValueError("planner_connection_invalid:" + provider_id)
        if provider_id in {"emhass", "akkudoktor_eos"}:
            url = validate_planner_url(row.get("url"))
            timeout = row.get("timeout_seconds", 30)
            if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 300:
                raise ValueError("planner_timeout_invalid:" + provider_id)
            normalized = {"url": url, "timeout_seconds": timeout}
            if provider_id == "akkudoktor_eos":
                protocol = row.get("protocol")
                if protocol not in ("legacy_optimize_v0", "v1_optimize"):
                    raise ValueError("eos_explicit_protocol_required")
                normalized["protocol"] = protocol
        else:
            entry_id = row.get("config_entry_id")
            if not isinstance(entry_id, str) or not entry_id.strip():
                raise ValueError("haeo_config_entry_required")
            normalized = {"config_entry_id": entry_id.strip()}
        result[provider_id] = normalized
    return result

def provider_states(options: dict[str, Any]) -> list[dict[str, Any]]:
    connections = configured_planners(options)
    rows = []
    for provider in PROVIDERS:
        configured = provider.provider_id in connections
        rows.append({
            "provider_id": provider.provider_id,
            "name": provider.label,
            "adapter": provider.adapter,
            "contract_status": provider.contract_status,
            "configuration_kind": provider.configuration_kind,
            "configured": configured,
            "execution_qualified": provider.execution_qualified and configured,
            "reason": provider.reason if configured else "connection_not_configured",
        })
    return rows

def available_selection_ids(options: dict[str, Any]) -> tuple[str, ...]:
    configured = configured_planners(options)
    requested = str(options.get("planner_provider") or "rhi_deterministic")
    # Keep the existing request visible after an upgrade even when unavailable.
    ids = [row.provider_id for row in PROVIDERS
           if row.provider_id in configured or row.provider_id == requested]
    return tuple(ids)

def execution_candidate(provider_id: str, *, provider_result_valid: bool, provider_data_current: bool) -> tuple[bool, str]:
    provider = provider_catalog().get(provider_id)
    if provider is None:
        return False, "unknown_planner_provider"
    if not provider.execution_qualified:
        return False, provider.reason or "planner_execution_not_qualified"
    if not provider_result_valid:
        return False, "planner_result_not_validated"
    if not provider_data_current:
        return False, "planner_inputs_stale"
    return True, "validated_selected_provider"

