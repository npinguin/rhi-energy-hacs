"""Bounded Energy-owned status envelope for Foundation 1.8 supervision.

Foundation receives only shared readiness and issue summaries. Energy properties,
bindings, planning evidence and V1 projection details remain in Energy diagnostics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .const import (
    DOMAIN,
    DOMAIN_ID,
    LEGACY_DIAGNOSTIC_ENTITIES,
    LEGACY_PUBLIC_ENTITIES,
    PUBLICATION_REVISION,
    PUBLIC_V2_ENTITY,
    RELEASE,
)
from .v1_parity import projection_consistency_issues

_PRIORITY = {
    "BLOCKED": 60,
    "STALE": 50,
    "CONFIGURATION_REQUIRED": 40,
    "DEGRADED": 30,
    "UNKNOWN": 20,
    "OK": 10,
    "READY": 10,
}


def _public_projection_functional(entity_id: str, projection: dict[str, Any]) -> bool:
    state = str(projection.get("state") or "UNAVAILABLE").upper()
    attrs = projection.get("attributes") or {}
    if state in {"AVAILABLE", "OK", "READY", "COMPLETE"}:
        return True
    if entity_id == "sensor.energy_metering_property_index" and state == "PARTIAL":
        return bool(attrs.get("period_summary_by_id")) and bool(attrs.get("selected_period_summary"))
    if entity_id == "sensor.energy_pricing_interval_index" and state == "PARTIAL":
        return bool(attrs.get("coverage_json")) and "interval_rows_json" in attrs
    if entity_id == "sensor.energy_value_accounting_index" and state in {"CONFIGURATION_REQUIRED", "NOT_EVALUATED"}:
        return "pricing_complete" in attrs and bool(attrs.get("product_status_json"))
    if entity_id == "sensor.energy_retrospective_event_index" and state in {
        "WAITING_FOR_METERING_BASELINE", "INSUFFICIENT_CLOSED_EVIDENCE"
    }:
        return bool(attrs.get("product_status_json")) and "events_json" in attrs
    return False


def _status(value: Any, *, configuration: bool = False) -> str:
    raw = str(value or "UNKNOWN").upper()
    mapping = {
        "CONFIGURED": "OK",
        "UNCONFIGURED": "CONFIGURATION_REQUIRED",
        "INVALID": "BLOCKED",
        "NOT_ACTIVE": "UNKNOWN",
        "AVAILABLE": "OK",
        "INCOMPLETE": "DEGRADED",
        "UNAVAILABLE": "DEGRADED",
        "PENDING": "DEGRADED",
    }
    normalized = mapping.get(raw, raw)
    if normalized not in _PRIORITY:
        return "CONFIGURATION_REQUIRED" if configuration and raw == "REQUIRED" else "UNKNOWN"
    return normalized


def _issue(
    issue_id: str,
    category: str,
    reason_code: str,
    *,
    blocking: bool,
    severity: str,
    scope: list[str],
) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "severity": severity,
        "category": category,
        "status": "OPEN",
        "reason_code": reason_code,
        "blocking": blocking,
        "affected_scope": scope,
        "first_seen": None,
        "last_seen": None,
        "details_reference": "rhi_energy:diagnostics",
    }


def _entry_is_loaded(entry: Any) -> bool:
    """Read ConfigEntry state without importing HA into the pure supervision contract."""
    state = getattr(entry, "state", None)
    value = getattr(state, "value", state)
    return str(value or "").lower() == "loaded"


def _mobility_runtime_expected(hass: Any) -> bool:
    """Return whether Mobility is actually loaded and therefore owes a publication.

    Persisted Foundation configuration can legitimately contain Mobility selections while
    the Mobility integration is disabled/unloaded. Energy must not turn that lifecycle
    state into an Energy runtime defect. Config-entry load state is used only for producer
    lifecycle expectation; producer semantics still come exclusively from Mobility's
    public contract.
    """
    try:
        entries = hass.config_entries.async_entries("rhi_mobility")
    except Exception:
        return False
    return any(_entry_is_loaded(entry) for entry in entries)


class EnergyDomainSupervision:
    """Synchronous, bounded provider consumed by Foundation's shared registry."""

    def __init__(self, hass: Any, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._last_success_at: str | None = None

    @property
    def _state(self) -> dict[str, Any]:
        value = (self.hass.data.get(DOMAIN) or {}).get(self.entry_id)
        return value if isinstance(value, dict) else {}

    def snapshot(self) -> dict[str, Any]:
        state = self._state
        manager = state.get("build_manager")
        runtime = state.get("runtime")
        runtime_snapshot = getattr(runtime, "snapshot", {}) or {}

        configuration_status = _status(
            getattr(manager, "configuration_status", None), configuration=True
        )
        foundation_status = _status(getattr(manager, "foundation_status", None))
        transport_record = state.get("public_transport")
        canonical_transport_status = (
            "BLOCKED"
            if isinstance(transport_record, dict) and transport_record.get("ready") is False
            else "OK"
        )
        contract_status = "OK" if foundation_status == "OK" and canonical_transport_status == "OK" else "BLOCKED"
        build_status = _status(getattr(manager, "build_health", None))
        runtime_status = _status(runtime_snapshot.get("health"))
        compatibility_entities = (*LEGACY_PUBLIC_ENTITIES, *LEGACY_DIAGNOSTIC_ENTITIES)
        live_public_count = sum(
            self.hass.states.get(entity_id) is not None
            for entity_id in compatibility_entities
        )
        compatibility_presence_status = (
            "OK" if live_public_count == len(compatibility_entities) else "BLOCKED"
        )
        projector = state.get("public_projector")
        product_states = {}
        projection_payloads: dict[str, dict[str, Any]] = {}
        canonical_public_v2: dict[str, Any] = {}
        if projector is not None and hasattr(projector, "get"):
            projection_payloads = {
                entity_id.removeprefix("sensor."): projector.get(entity_id.removeprefix("sensor."))
                for entity_id in LEGACY_PUBLIC_ENTITIES
            }
            product_states = {
                entity_id: str(
                    projection_payloads.get(entity_id.removeprefix("sensor."), {}).get("state")
                    or "UNAVAILABLE"
                ).upper()
                for entity_id in LEGACY_PUBLIC_ENTITIES
            }
            if hasattr(projector, "get_parity_source"):
                canonical_public_v2 = projector.get_parity_source() or {}
            elif hasattr(projector, "get_v2"):
                canonical_public_v2 = projector.get_v2() or {}
        canonical_parity_issues = (
            projection_consistency_issues(projection_payloads, canonical_public_v2)
            if projection_payloads and canonical_public_v2
            else {}
        )
        # Functional availability is an installation/runtime concern, not V1/V2 parity.
        # Compatibility blocks only when the frozen surface is missing or when V1
        # contradicts canonical V2 truth for an equivalent fact.
        degraded_public_entities = sorted(canonical_parity_issues)
        compatibility_functional_status = (
            compatibility_presence_status if not product_states
            else "DEGRADED" if canonical_parity_issues
            else "OK"
        )
        mobility_available = bool(runtime_snapshot.get("mobility_publication_available"))
        mobility_expected = _mobility_runtime_expected(self.hass)

        issues: list[dict[str, Any]] = []
        if configuration_status != "OK":
            issues.append(_issue(
                "energy:configuration:readiness", "CONFIGURATION",
                f"ENERGY_CONFIGURATION_{configuration_status}",
                blocking=configuration_status in {"BLOCKED", "STALE"},
                severity="ERROR" if configuration_status in {"BLOCKED", "STALE"} else "WARNING",
                scope=["energy"],
            ))
        if foundation_status != "OK":
            issues.append(_issue(
                "energy:contract:foundation_handoff", "CONTRACT",
                f"FOUNDATION_HANDOFF_{contract_status}", blocking=True,
                severity="CRITICAL", scope=["SelectedDomainBuildInput"],
            ))
        if canonical_transport_status != "OK":
            issues.append(_issue(
                "energy:contract:public_v2_transport", "CONTRACT",
                "PUBLIC_V2_CANONICAL_TRANSPORT_UNAVAILABLE", blocking=True,
                severity="CRITICAL", scope=[PUBLIC_V2_ENTITY],
            ))
        if build_status != "OK":
            issues.append(_issue(
                "energy:build:domain_model", "BINDING",
                f"ENERGY_BUILD_{build_status}",
                blocking=build_status in {"BLOCKED", "STALE"},
                severity="ERROR" if build_status in {"BLOCKED", "STALE"} else "WARNING",
                scope=["EnergyDomainModel"],
            ))
        if runtime_status != "OK":
            issues.append(_issue(
                "energy:runtime:canonical_truth", "RUNTIME",
                f"ENERGY_RUNTIME_{runtime_status}",
                blocking=runtime_status in {"BLOCKED", "STALE"},
                severity="ERROR" if runtime_status in {"BLOCKED", "STALE"} else "WARNING",
                scope=["EnergyRuntime"],
            ))
        if compatibility_presence_status != "OK":
            issues.append(_issue(
                "energy:compatibility:v1_contract_presence", "COMPATIBILITY",
                "V1_FEATURE_PARITY_INCOMPLETE", blocking=False,
                severity="WARNING", scope=["R1.89.44_CONTRACT"],
            ))
        elif compatibility_functional_status != "OK":
            issues.append(_issue(
                "energy:compatibility:v1_feature_parity", "COMPATIBILITY",
                "V1_FEATURE_PARITY_FUNCTIONALLY_INCOMPLETE", blocking=False,
                severity="WARNING", scope=degraded_public_entities[:12] or ["R1.89.44_CONTRACT"],
            ))
        if mobility_expected and not mobility_available:
            issues.append(_issue(
                "energy:dependency:mobility_publication", "DEPENDENCY",
                "MOBILITY_PUBLICATION_UNAVAILABLE", blocking=False,
                severity="WARNING", scope=["sensor.mobility_energy_asset_publication"],
            ))

        # V1 is a temporary downstream compatibility projection. Its presence or
        # parity may be diagnosed, but it can never govern canonical V2 readiness.
        canonical_statuses = [
            configuration_status,
            contract_status,
            build_status,
            runtime_status,
        ]
        overall = max(canonical_statuses, key=lambda value: _PRIORITY[value])
        if all(value == "OK" for value in canonical_statuses):
            overall = "READY"

        observed_at = datetime.now(timezone.utc).isoformat()
        if overall == "READY":
            self._last_success_at = observed_at
        return {
            "contract_id": "RHI_DOMAIN_SUPERVISORY_STATUS_V1",
            "contract_version": "1.1.0",
            "domain_id": DOMAIN_ID,
            "publisher_domain": DOMAIN,
            "release": RELEASE,
            "configuration_revision": max(0, int(getattr(manager, "configuration_revision", 0) or 0)),
            "build_input_revision": max(0, int(getattr(manager, "build_input_revision", 0) or 0)),
            "publication_revision": PUBLICATION_REVISION,
            "configuration_status": configuration_status,
            "contract_status": contract_status,
            "build_status": build_status,
            "runtime_status": runtime_status,
            "overall_domain_readiness": overall,
            "issue_count": len(issues),
            "blocking_issue_count": sum(bool(item["blocking"]) for item in issues),
            "warning_count": sum(item["severity"] == "WARNING" for item in issues),
            "issues_summary": issues,
            "last_success_at": self._last_success_at,
            "last_observed_at": observed_at,
            "details_reference": "rhi_energy:diagnostics",
        }


def register_domain_supervision(
    hass: Any, provider: EnergyDomainSupervision
) -> Callable[[], None]:
    """Register supervision and return the generation owned by this Energy load."""
    from custom_components.rhi_foundation.shared_registry import (
        register_domain_supervisory_status_provider,
    )

    unsubscribe = register_domain_supervisory_status_provider(
        hass,
        domain_id=DOMAIN_ID,
        publisher_domain=DOMAIN,
        provider=provider,
    )
    if callable(unsubscribe):
        return unsubscribe

    # Foundation 1.8.1 compatibility: registration returned None.
    def _legacy_unsubscribe() -> None:
        unregister_domain_supervision(hass, provider)

    return _legacy_unsubscribe


def unregister_domain_supervision(hass: Any, provider: EnergyDomainSupervision) -> None:
    """Legacy/admin cleanup through Foundation-owned registry mechanics."""
    from custom_components.rhi_foundation.shared_registry import (
        unregister_domain_supervisory_status_provider,
    )

    unregister_domain_supervisory_status_provider(
        hass,
        domain_id=DOMAIN_ID,
        publisher_domain=DOMAIN,
    )
