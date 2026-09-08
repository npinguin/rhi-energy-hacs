"""Consume Foundation SelectedDomainBuildInput 1.2.0 and own Energy rebuild lifecycle."""
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant

from ..compilers.energy import compile_energy_build_inputs
from ..const import BUILD_INPUT_REGISTRY_KEY, SELECTED_BUILD_INPUTS_CHANGED_EVENT

_LOGGER = logging.getLogger(__name__)
DOMAIN_ID = "energy"
SELECTED_INPUT_CONTRACT_VERSION = "1.2.0"
FOUNDATION_CANDIDATE_CONTRACT_VERSION = "1.1.0"


def _candidate_evidence_index(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate in entry.get("candidate_evidence") or []:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id:
            result[candidate_id] = candidate
    return result


def _matches_by_candidate(group: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for match in group.get("candidate_matches") or []:
        if not isinstance(match, dict):
            continue
        candidate_id = str(match.get("candidate_id") or "")
        if candidate_id:
            result.setdefault(candidate_id, []).append(match)
    return result


def _candidate_and_match_complete(candidate: dict[str, Any], match: dict[str, Any]) -> bool:
    if candidate.get("kind") != "foundation_capability_candidate":
        return False
    if candidate.get("contract_version") != FOUNDATION_CANDIDATE_CONTRACT_VERSION:
        return False
    for field in ("source_identity", "technical_capability", "evidence", "quality", "safety"):
        if not isinstance(candidate.get(field), dict):
            return False

    source = candidate.get("source_identity") or {}
    published = match.get("published_match") or {}
    if not all(match.get(key) for key in ("integration_domain", "raw_capability_id", "source_kind")):
        return False
    if not isinstance(published, dict) or not published.get("all_of"):
        return False
    for key in ("integration_domain", "raw_capability_id", "source_kind"):
        if match.get(key) != published.get(key):
            return False
    if source.get("integration_domain") != match.get("integration_domain"):
        return False
    if source.get("source_kind") != match.get("source_kind"):
        return False
    if not source.get("target_scope"):
        return False
    return True


def _selection_explicitly_empty(entry: dict[str, Any]) -> bool:
    """Return True only for explicit user intent that this concept has zero objects.

    Publication support does not imply an installed/configured instance.  An empty
    specific-device selection is authoritative user intent.  all_matching with no
    candidates is *not* treated as absence because that can also mean matching failed.
    """
    selection = entry.get("selection") or {}
    if selection.get("device_filter_mode") != "specific_devices":
        return False
    selected = [str(value) for value in selection.get("selected_device_ids") or [] if str(value)]
    return not selected


def _selected_handoff_complete(entry: dict[str, Any]) -> bool:
    """Validate complete self-contained 1.2.0 selected handoff and raw-match attribution."""
    if entry.get("kind") != "selected_domain_build_input":
        return False
    if entry.get("contract_version") != SELECTED_INPUT_CONTRACT_VERSION:
        return False
    if _selection_explicitly_empty(entry):
        return True
    evidence = _candidate_evidence_index(entry)
    for group in entry.get("candidate_groups") or []:
        if not isinstance(group, dict) or not group.get("input_id"):
            return False
        ids = [str(value) for value in group.get("candidate_ids") or []]
        if int(group.get("candidate_count") or 0) != len(ids):
            return False
        matches = _matches_by_candidate(group)
        for candidate_id in ids:
            candidate = evidence.get(candidate_id)
            candidate_matches = matches.get(candidate_id) or []
            if not candidate or not candidate_matches:
                return False
            # A candidate can satisfy alternative published rules, but all selected
            # matches for this normalized input must resolve to one domain-owned raw
            # capability identity. Otherwise semantic attribution is ambiguous.
            raw_ids = {str(item.get("raw_capability_id") or "") for item in candidate_matches}
            if "" in raw_ids or len(raw_ids) != 1:
                return False
            if not all(_candidate_and_match_complete(candidate, item) for item in candidate_matches):
                return False
    # Zero candidates is a structurally valid handoff. Semantic applicability is
    # evaluated by the Energy compiler from selection intent + discovery assessment.
    return True


def _candidate_count(entry: dict[str, Any]) -> int:
    return sum(
        len(group.get("candidate_ids") or [])
        for group in (entry.get("candidate_groups") or [])
        if isinstance(group, dict)
    )


def _required_candidate_count(entry: dict[str, Any]) -> int:
    """Count only candidates that prove presence of a usable concept instance.

    Optional evidence such as a write surface or forecast power may exist without the
    required semantic measurements that make the concept buildable. For all_matching
    selections, such optional-only evidence must never turn an optional concept into a
    blocked/invalid instance.
    """
    return sum(
        len(group.get("candidate_ids") or [])
        for group in (entry.get("candidate_groups") or [])
        if isinstance(group, dict) and group.get("required") is True
    )


def _builder_assessment(entry: dict[str, Any], *, structural_valid: bool = True) -> dict[str, Any]:
    selection = entry.get("selection") or {}
    discovery = entry.get("discovery_assessment") or {}
    selected_ids = [str(value) for value in selection.get("selected_device_ids") or [] if str(value)]
    candidate_count = _candidate_count(entry)
    required_candidate_count = _required_candidate_count(entry)
    mode = str(selection.get("device_filter_mode") or "unknown")
    concept = str(selection.get("concept") or "unknown")
    integration = str(selection.get("integration_domain") or "unknown")

    if not structural_valid:
        status = "INVALID_ATTRIBUTION"
    elif mode == "specific_devices" and not selected_ids:
        status = "ABSENT"
    elif mode == "all_matching" and candidate_count == 0:
        status = "ABSENT"
    elif mode == "all_matching" and required_candidate_count == 0:
        # Auxiliary-only evidence is worth normalizing/diagnosing, but it cannot prove
        # a complete runtime instance. The compiler may safely publish a degraded subset.
        status = "DEGRADED"
    elif discovery.get("required_inputs_complete") and not discovery.get("review_required") and discovery.get("topology_state") == "unambiguous":
        status = "READY"
    elif discovery.get("review_required"):
        status = "BLOCKED"
    else:
        status = "INCOMPLETE"

    return {
        "builder_id": entry.get("builder_id"),
        "concept": concept,
        "integration_domain": integration,
        "status": status,
        "selection_mode": mode,
        "selected_device_count": len(selected_ids),
        "candidate_count": candidate_count,
        "required_candidate_count": required_candidate_count,
        "presence_basis": (
            "explicit_specific_selection" if mode == "specific_devices" and selected_ids
            else "explicit_empty_selection" if mode == "specific_devices"
            else "required_candidates" if required_candidate_count > 0
            else "auxiliary_candidates" if candidate_count > 0
            else "no_candidates"
        ),
        "required_inputs_complete": discovery.get("required_inputs_complete"),
        "topology_state": discovery.get("topology_state"),
        "review_required": discovery.get("review_required"),
        "issues": [str(value) for value in (discovery.get("issues") or [])][:20],
    }


def _materialize_compiler_input(entry: dict[str, Any]) -> dict[str, Any]:
    """Create Energy-local compiler view solely from SelectedDomainBuildInput 1.2.0.

    Each selected Foundation candidate is augmented with the exact domain-owned raw
    match that selected it. No HA registry scan and no Foundation-private state is read.
    """
    result = deepcopy(entry)
    evidence = _candidate_evidence_index(entry)
    groups: list[dict[str, Any]] = []
    for group in entry.get("candidate_groups") or []:
        if not isinstance(group, dict):
            continue
        row = deepcopy(group)
        matches = _matches_by_candidate(group)
        candidates: list[dict[str, Any]] = []
        for candidate_id in group.get("candidate_ids") or []:
            candidate = evidence.get(str(candidate_id))
            if candidate is None:
                continue
            selected_matches = matches.get(str(candidate_id)) or []
            # Completeness validation guarantees one raw_capability_id. Preserve the
            # first exact published match and all alternatives for diagnostics.
            materialized = deepcopy(candidate)
            materialized["selected_match"] = deepcopy(selected_matches[0])
            materialized["selected_matches"] = deepcopy(selected_matches)
            candidates.append(materialized)
        row["candidates"] = candidates
        groups.append(row)
    result["candidate_groups"] = groups
    return result


class EnergyBuildManager:
    """Own Energy semantic validation, compile and atomic runtime model activation."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.compiled_model: dict[str, Any] | None = None
        self.foundation_status = "UNKNOWN"
        self.build_health = "UNKNOWN"
        self.reason = "selected_domain_build_input_missing"
        self.configuration_revision = 0
        self.build_input_revision = 0
        self.last_configuration_revision = 0
        self.handoff_present = False
        self.configuration_status = "UNCONFIGURED"
        self.last_success: str | None = None
        self.builder_assessments: dict[str, dict[str, Any]] = {}
        self.affected_scope: list[str] = []
        self._callbacks: list[Callable[[], None]] = []
        self._model_callbacks: list[Callable[[dict[str, Any] | None], None]] = []
        self._unsubscribe_event: Callable[[], None] | None = None

    def add_callback(self, cb):
        self._callbacks.append(cb)
        return lambda: self._callbacks.remove(cb) if cb in self._callbacks else None

    def add_model_callback(self, cb):
        self._model_callbacks.append(cb)
        return lambda: self._model_callbacks.remove(cb) if cb in self._model_callbacks else None

    def _notify(self) -> None:
        for cb in tuple(self._callbacks):
            cb()

    def _notify_model(self) -> None:
        for cb in tuple(self._model_callbacks):
            cb(self.compiled_model)

    def _current_entry(self) -> dict[str, Any]:
        registry = self.hass.data.get(BUILD_INPUT_REGISTRY_KEY, {}) or {}
        entry = registry.get(DOMAIN_ID) or {}
        return entry if isinstance(entry, dict) else {}

    @property
    def entity_inventory_authoritative(self) -> bool:
        """Whether HA may reconcile/remove logical entity registry rows."""
        if self.reason == "selected_domain_build_input_removed":
            return True
        return bool(
            self.handoff_present
            and self.foundation_status == "OK"
            and self.compiled_model is not None
            and self.build_health in {"OK", "DEGRADED"}
        )

    def _deactivate_for_removed_handoff(self) -> None:
        changed = self.compiled_model is not None
        self.compiled_model = None
        self.foundation_status = "UNKNOWN"
        self.build_health = "UNKNOWN"
        self.reason = "selected_domain_build_input_removed"
        self.handoff_present = False
        self.configuration_status = "UNCONFIGURED"
        self.configuration_revision = 0
        self.build_input_revision = 0
        self.builder_assessments = {}
        self.affected_scope = []
        if changed:
            self._notify_model()
        self._notify()

    def rebuild(self, reason: str) -> bool:
        entry = self._current_entry()
        if not entry:
            # Domain-before-Foundation is valid. A missing current registry entry is
            # never inferred from an old revision. Retain last-good runtime only as STALE.
            self.handoff_present = False
            self.foundation_status = "UNKNOWN"
            self.build_health = "STALE" if self.compiled_model else "UNKNOWN"
            self.configuration_status = "STALE" if self.compiled_model else "UNCONFIGURED"
            self.reason = "selected_domain_build_input_missing"
            self.builder_assessments = {}
            self.affected_scope = []
            self._notify()
            return False

        inputs = [item for item in (entry.get("inputs") or []) if isinstance(item, dict)]
        self.handoff_present = True
        self.configuration_revision = int(entry.get("configuration_revision") or 0)
        self.last_configuration_revision = self.configuration_revision
        self.build_input_revision = max(
            [int(item.get("build_input_revision") or 0) for item in inputs],
            default=self.configuration_revision,
        )

        wrong_contract = [
            str(item.get("builder_id") or "unknown")
            for item in inputs
            if item.get("contract_version") != SELECTED_INPUT_CONTRACT_VERSION
        ]
        if wrong_contract:
            self.foundation_status = "INVALID"
            self.configuration_status = "INVALID"
            self.build_health = "STALE" if self.compiled_model else "INVALID"
            self.reason = "selected_build_input_contract_version_unsupported"
            self.builder_assessments = {
                str(item.get("builder_id") or "unknown"): _builder_assessment(item, structural_valid=False)
                for item in inputs
            }
            self.affected_scope = sorted(wrong_contract)[:20]
            _LOGGER.error("Energy requires SelectedDomainBuildInput 1.2.0; builders=%s", wrong_contract)
            self._notify()
            return False

        structurally_invalid: list[str] = []
        payload: dict[str, dict[str, Any]] = {}
        assessments: dict[str, dict[str, Any]] = {}
        preflight_issues: list[str] = []
        for item in inputs:
            builder_id = str(item.get("builder_id") or "unknown")
            valid = _selected_handoff_complete(item)
            assessments[builder_id] = _builder_assessment(item, structural_valid=valid)
            if not valid:
                structurally_invalid.append(builder_id)
                preflight_issues.append(f"{builder_id}:selected_build_input_raw_match_evidence_invalid")
                continue
            if item.get("builder_id"):
                payload[builder_id] = _materialize_compiler_input(item)

        # Configuration is valid once the authoritative registry entry and supported
        # contracts are present. Per-builder discovery/semantic problems belong to build.
        self.foundation_status = "OK"
        self.configuration_status = "CONFIGURED"
        self.builder_assessments = assessments

        try:
            model = compile_energy_build_inputs(
                payload,
                self.compiled_model,
                preflight_issues=preflight_issues,
            )
        except Exception as exc:
            # Atomic safety: never replace previous known-good model after an unexpected
            # compiler failure. Normal per-builder failures are returned as model issues.
            self.build_health = "STALE" if self.compiled_model else "INVALID"
            self.reason = str(exc).split(":", 1)[0] or "semantic_compile_failed"
            self.affected_scope = sorted(structurally_invalid)[:20]
            _LOGGER.warning("Energy semantic compile blocked during %s: %s", reason, exc)
            self._notify()
            return False

        model_issues = [str(value) for value in (model.get("issues") or [])]
        compile_assessments = model.get("concept_assessments") or {}
        # Compiler truth refines Foundation discovery truth. Keep both, but expose the
        # normalization result as the operator-facing status for each builder.
        for builder_id, compile_row in compile_assessments.items():
            if builder_id not in self.builder_assessments:
                self.builder_assessments[builder_id] = {"builder_id": builder_id}
            self.builder_assessments[builder_id]["normalization"] = deepcopy(compile_row)
            self.builder_assessments[builder_id]["status"] = compile_row.get("status") or self.builder_assessments[builder_id].get("status")

        affected = sorted({
            builder_id
            for builder_id, row in self.builder_assessments.items()
            if str(row.get("status") or "") in {"BLOCKED", "DEGRADED", "INVALID_ATTRIBUTION"}
        })
        self.affected_scope = affected[:20]

        changed = model != self.compiled_model
        self.compiled_model = model
        if not model_issues:
            self.build_health = "OK"
            self.reason = "compiled_model_ready"
        else:
            # Structural/configuration defects are handled before compilation. Once the
            # handoff is structurally valid, per-concept defects are a degraded build,
            # never a reason to suppress safely normalized unrelated concepts.
            self.build_health = "DEGRADED"
            self.reason = "partial_concept_compile"
        self.last_success = reason if self.build_health in {"OK", "DEGRADED"} else self.last_success

        if changed:
            _LOGGER.info(
                "Energy compiled model activated revision=%s concepts=%s absent=%s issues=%s reason=%s",
                model.get("compiled_model_revision"),
                sorted((model.get("concepts") or {}).keys()),
                model.get("explicitly_absent_concepts") or [],
                len(model_issues),
                reason,
            )
            self._notify_model()
        self._notify()
        return self.build_health in {"OK", "DEGRADED"}

    async def _async_selected_inputs_changed(self, event: Event) -> None:
        data = event.data or {}
        if data.get("domain_id") != DOMAIN_ID:
            return
        reason = str(data.get("reason") or "refreshed")
        if reason == "removed":
            self._deactivate_for_removed_handoff()
            return
        # Event data is structural only. Always re-read authoritative registry.
        self.rebuild(f"foundation_event:{reason}")

    async def async_start(self) -> None:
        if self._unsubscribe_event is None:
            self._unsubscribe_event = self.hass.bus.async_listen(
                SELECTED_BUILD_INPUTS_CHANGED_EVENT,
                self._async_selected_inputs_changed,
            )
        self.rebuild("startup")

    async def async_refresh(self, reason: str = "explicit_refresh") -> bool:
        return self.rebuild(reason)

    async def async_stop(self) -> None:
        if self._unsubscribe_event is not None:
            self._unsubscribe_event()
            self._unsubscribe_event = None
