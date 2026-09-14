from __future__ import annotations

from copy import deepcopy

from .public_contract import PublicContractProjector as BaseProjector, project_all
from .public_v2_parity import build_public_contract_v2, published_v2
from .v1_parity import close_v1_projection


class PublicContractProjector(BaseProjector):
    def recompute(self) -> None:
        snapshot = deepcopy(self.runtime.snapshot)
        model = self.manager.compiled_model or {}
        battery = (model.get("concepts") or {}).get("battery_system") or {}
        snapshot["battery_reserve_write_supported"] = bool(battery.get("reserve_binding"))
        snapshot["settings"] = deepcopy(self.store.data.get("settings") or {})
        rows = self.interaction.command_rows()
        v2_contract = build_public_contract_v2(snapshot, self.store.data, rows, model)
        public_v2 = published_v2(v2_contract)
        v2_changed = public_v2 != self._v2
        projected = close_v1_projection(
            project_all(v2_contract, self.store.data, rows, self.manager), public_v2
        )
        self._v2 = public_v2
        for object_id, payload in projected.items():
            if payload != self._cache.get(object_id):
                self._cache[object_id] = payload
                for callback in tuple(self._callbacks.get(object_id, [])):
                    callback()
        if v2_changed:
            for callback in tuple(self._callbacks.get("__public_v2__", [])):
                callback()
