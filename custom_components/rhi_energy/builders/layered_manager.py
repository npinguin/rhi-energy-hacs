"""Generation-safe layered lifecycle around the proven Energy semantic manager."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from .build_manager import EnergyBuildManager as _SemanticBuildManager
from ..compilers.layered_model import materialize_layered_energy_model
from ..const import SELECTED_BUILD_INPUTS_CHANGED_EVENT

_LAYER_KEYS = {
    "layer_contract_version",
    "logical_layer",
    "system_assets",
    "planning_assets",
    "intelligence_assets",
    "dependencies",
    "model_fingerprint",
    "dependency_diagnostics",
    "runtime_rules",
    "generation",
    "layer_health",
    "materialization_records",
}


def _semantic_model(model: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip derived layer metadata before handing last-good state to L1 compiler."""
    if model is None:
        return None
    out = deepcopy(model)
    for key in _LAYER_KEYS:
        out.pop(key, None)
    return out


def _registry_revisions(manager: _SemanticBuildManager) -> tuple[int, int]:
    """Read structural revision only from Foundation's authoritative registry."""
    entry = manager._current_entry()
    if not entry:
        return 0, 0
    configuration_revision = int(entry.get("configuration_revision") or 0)
    inputs = [row for row in (entry.get("inputs") or []) if isinstance(row, dict)]
    build_input_revision = max(
        [int(row.get("build_input_revision") or 0) for row in inputs],
        default=configuration_revision,
    )
    return configuration_revision, build_input_revision


class LayeredEnergyBuildManager(_SemanticBuildManager):
    """Compile and atomically activate one complete Energy generation at a time."""

    def __init__(self, hass) -> None:
        super().__init__(hass)
        self._structural_lock = asyncio.Lock()
        self.active_generation_id: str | None = None

    def _activate_layers(self, model: dict[str, Any]) -> dict[str, Any]:
        model.update(materialize_layered_energy_model(model))
        generation = {
            "generation_id": (
                f"energy:{model.get('compiled_model_revision')}:"
                f"{model.get('model_fingerprint')}"
            ),
            "compiled_model_revision": model.get("compiled_model_revision"),
            "compiled_from_configuration_revision": self.configuration_revision,
            "compiled_from_build_input_revision": self.build_input_revision,
            "state": "ACTIVE",
        }
        model["generation"] = generation
        self.active_generation_id = str(generation["generation_id"])
        return model

    def rebuild(self, reason: str) -> bool:
        configuration_revision, build_input_revision = _registry_revisions(self)
        active_generation = self.compiled_model

        if (
            active_generation is not None
            and configuration_revision
            and configuration_revision < self.last_configuration_revision
        ):
            self.foundation_status = "STALE"
            self.configuration_status = "STALE"
            self.build_health = "STALE"
            self.reason = "selected_domain_build_input_revision_regressed"
            self._notify()
            return False

        if (
            active_generation is not None
            and configuration_revision == self.configuration_revision
            and build_input_revision == self.build_input_revision
            and configuration_revision > 0
        ):
            # Foundation events invalidate; revisions decide whether structure changed.
            return self.build_health in {"OK", "DEGRADED"}

        callbacks = self._callbacks
        model_callbacks = self._model_callbacks
        self._callbacks = []
        self._model_callbacks = []
        self.compiled_model = _semantic_model(active_generation)
        try:
            accepted = super().rebuild(reason)
            candidate = self.compiled_model
        finally:
            self._callbacks = callbacks
            self._model_callbacks = model_callbacks

        if not accepted or candidate is None:
            # A failed candidate may update diagnostics, never the active topology.
            if active_generation is not None:
                self.compiled_model = active_generation
            self._notify()
            return False

        candidate = self._activate_layers(candidate)
        changed = candidate != active_generation
        self.compiled_model = candidate
        if changed:
            self._notify_model()
        self._notify()
        return True

    def _deactivate_for_removed_handoff(self) -> None:
        super()._deactivate_for_removed_handoff()
        self.last_configuration_revision = 0
        self.active_generation_id = None

    async def _serialized_rebuild(self, reason: str) -> bool:
        async with self._structural_lock:
            return self.rebuild(reason)

    async def _async_selected_inputs_changed(self, event) -> None:
        data = event.data or {}
        if data.get("domain_id") != "energy":
            return
        reason = str(data.get("reason") or "refreshed")
        async with self._structural_lock:
            if reason == "removed":
                self._deactivate_for_removed_handoff()
                return
            self.rebuild(f"foundation_event:{reason}")

    async def async_start(self) -> None:
        # Subscribe before authoritative import so startup cannot miss a revision change.
        if self._unsubscribe_event is None:
            self._unsubscribe_event = self.hass.bus.async_listen(
                SELECTED_BUILD_INPUTS_CHANGED_EVENT,
                self._async_selected_inputs_changed,
            )
        await self._serialized_rebuild("startup")

    async def async_refresh(self, reason: str = "explicit_refresh") -> bool:
        return await self._serialized_rebuild(reason)
