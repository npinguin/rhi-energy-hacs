"""Bounded Energy-owned status envelope for Foundation 1.8 supervision.

Foundation receives only shared readiness and issue summaries. Energy properties,
bindings and planning evidence remain in Energy diagnostics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .const import (
    DOMAIN,
    DOMAIN_ID,
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
        contract_status = "OK" if foundation_status == "OK" else "BLOCKED"
        build_status = _status(getattr(manager, "build_health", None))
        runtime_status = _status(runtime_snapshot.get("health"))
        mobility_available = bool(runtime_snapshot.get("mobility_publication_available"))
        mobility_expected = _mobility_runtime_expected(self.hass)
        canonical_coverage = runtime_snapshot.get("canonical_coverage") or {}
        canonical_coverage_status = (
            "OK" if canonical_coverage.get("complete") is True
            else "UNKNOWN" if not canonical_coverage else "BLOCKED"
        )

        builder_assessments = getattr(manager, "builder_assessments", {}) or {}
        builder_issue_rows = [
            str(issue)
            for assessment in builder_assessments.values()
            if isinstance(assessment, dict)
            for issue in (assessment.get("issues") or [])
            if issue
        ]

        logical_assets = [
            row for row in (runtime_snapshot.get("logical_assets") or [])
            if isinstance(row, dict) and row.get("asset_id")
        ]
        logical_by_id = {str(row["asset_id"]): row for row in logical_assets}
        def _has_inverter_ancestor(row: dict[str, Any]) -> bool:
            seen: set[str] = set()
            current = row
            while isinstance(current, dict):
                parent_id = str(current.get("parent_asset_id") or "")
                if not parent_id or parent_id in seen:
                    return False
                seen.add(parent_id)
                parent = logical_by_id.get(parent_id)
                if parent is None:
                    return False
                if str(parent.get("object_class") or "") == "solar_inverter":
                    return True
                current = parent
            return False

        unresolved_solar_hierarchy = [
            str(row.get("asset_id"))
            for row in logical_assets
            if str(row.get("object_class") or "") in {"solar_zone", "solar_optimizer"}
            and not _has_inverter_ancestor(row)
        ]

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
        if canonical_coverage_status != "OK":
            scope = (
                canonical_coverage.get("unpublished_accepted_binding_ids")
                or canonical_coverage.get("unclassified_property_ids")
                or canonical_coverage.get("unexplained_resolution_property_ids")
                or ["EnergyRuntime"]
            )
            issues.append(_issue(
                "energy:contract:canonical_coverage", "CONTRACT",
                "CANONICAL_PRODUCT_COVERAGE_INCOMPLETE",
                blocking=True,
                severity="ERROR",
                scope=[str(value) for value in scope[:12]],
            ))
        if builder_issue_rows:
            issues.append(_issue(
                "energy:build:selected_input_assessment", "BINDING",
                "SELECTED_INPUT_ASSESSMENT_ISSUES", blocking=False,
                severity="WARNING", scope=["EnergyDomainModel"],
            ))
        if unresolved_solar_hierarchy:
            issues.append(_issue(
                "energy:topology:solar_inverter_hierarchy", "TOPOLOGY",
                "SOLAR_INVERTER_PARENT_UNRESOLVED", blocking=False,
                severity="WARNING", scope=unresolved_solar_hierarchy[:12],
            ))
        if mobility_expected and not mobility_available:
            issues.append(_issue(
                "energy:dependency:mobility_publication", "DEPENDENCY",
                "MOBILITY_PUBLICATION_UNAVAILABLE", blocking=False,
                severity="WARNING", scope=["sensor.mobility_energy_asset_publication"],
            ))

        # Canonical Energy runtime is the readiness authority.
        canonical_statuses = [
            configuration_status,
            contract_status,
            build_status,
            runtime_status,
            canonical_coverage_status,
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
