"""Bounded Energy-owned status envelope for Foundation 1.8 supervision.

Foundation receives only shared readiness and issue summaries. Energy properties,
bindings, planning evidence and V1 projection details remain in Energy diagnostics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .const import (
    DOMAIN,
    DOMAIN_ID,
    LEGACY_DIAGNOSTIC_ENTITIES,
    LEGACY_PUBLIC_ENTITIES,
    PUBLICATION_REVISION,
    RELEASE,
)

_PRIORITY = {
    "BLOCKED": 60,
    "STALE": 50,
    "CONFIGURATION_REQUIRED": 40,
    "DEGRADED": 30,
    "UNKNOWN": 20,
    "OK": 10,
    "READY": 10,
}


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
        contract_status = "OK" if foundation_status == "OK" else "BLOCKED"
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
        if projector is not None and hasattr(projector, "get"):
            product_states = {
                entity_id: str(projector.get(entity_id.removeprefix("sensor.")).get("state") or "UNAVAILABLE").upper()
                for entity_id in LEGACY_PUBLIC_ENTITIES
            }
        healthy_public_states = {"AVAILABLE", "OK", "READY", "COMPLETE"}
        degraded_public_entities = sorted(
            entity_id for entity_id, value in product_states.items()
            if value not in healthy_public_states
        )
        compatibility_functional_status = (
            compatibility_presence_status if not product_states
            else "DEGRADED" if degraded_public_entities
            else "OK"
        )
        mobility_available = bool(runtime_snapshot.get("mobility_publication_available"))

        issues: list[dict[str, Any]] = []
        if configuration_status != "OK":
            issues.append(_issue(
                "energy:configuration:readiness", "CONFIGURATION",
                f"ENERGY_CONFIGURATION_{configuration_status}",
                blocking=configuration_status in {"BLOCKED", "STALE"},
                severity="ERROR" if configuration_status in {"BLOCKED", "STALE"} else "WARNING",
                scope=["energy"],
            ))
        if contract_status != "OK":
            issues.append(_issue(
                "energy:contract:foundation_handoff", "CONTRACT",
                f"FOUNDATION_HANDOFF_{contract_status}", blocking=True,
                severity="CRITICAL", scope=["SelectedDomainBuildInput"],
            ))
        if build_status != "OK":
            issues.append(_issue(
                "energy:build:compiled_model", "BINDING",
                f"ENERGY_BUILD_{build_status}",
                blocking=build_status in {"BLOCKED", "STALE"},
                severity="ERROR" if build_status in {"BLOCKED", "STALE"} else "WARNING",
                scope=["CompiledEnergyModel"],
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
                "V1_FEATURE_PARITY_INCOMPLETE", blocking=True,
                severity="CRITICAL", scope=["R1.89.44_CONTRACT"],
            ))
        elif compatibility_functional_status != "OK":
            issues.append(_issue(
                "energy:compatibility:v1_feature_parity", "COMPATIBILITY",
                "V1_FEATURE_PARITY_FUNCTIONALLY_INCOMPLETE", blocking=False,
                severity="WARNING", scope=degraded_public_entities[:12] or ["R1.89.44_CONTRACT"],
            ))
        if "mobility_publication_available" in runtime_snapshot and not mobility_available:
            issues.append(_issue(
                "energy:dependency:mobility_publication", "DEPENDENCY",
                "MOBILITY_PUBLICATION_UNAVAILABLE", blocking=False,
                severity="WARNING", scope=["sensor.mobility_energy_asset_publication"],
            ))

        statuses = [
            configuration_status,
            contract_status,
            build_status,
            runtime_status,
            compatibility_presence_status,
            compatibility_functional_status,
        ]
        overall = max(statuses, key=lambda value: _PRIORITY[value])
        if all(value == "OK" for value in statuses):
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

def register_domain_supervision(hass: Any, provider: EnergyDomainSupervision) -> None:
    """Register through Foundation-owned 1.8.1 registry mechanics."""
    from custom_components.rhi_foundation.shared_registry import (
        register_domain_supervisory_status_provider,
    )

    register_domain_supervisory_status_provider(
        hass,
        domain_id=DOMAIN_ID,
        publisher_domain=DOMAIN,
        provider=provider,
    )


def unregister_domain_supervision(hass: Any, provider: EnergyDomainSupervision) -> None:
    """Unregister through Foundation-owned 1.8.1 registry mechanics."""
    from custom_components.rhi_foundation.shared_registry import (
        unregister_domain_supervisory_status_provider,
    )

    unregister_domain_supervisory_status_provider(
        hass,
        domain_id=DOMAIN_ID,
        publisher_domain=DOMAIN,
    )
