"""Domain runtime auxiliary behavior; no separate runtime authority."""
from __future__ import annotations
from typing import Any
from .layer_readiness import evaluate_runtime_layers

class EnergyRuntimeAuxiliary:
    def _evaluate_runtime_layers(
        self,
        facts: dict[str, Any],
        flexible: list[dict[str, Any]],
        logical_assets: list[dict[str, Any]],
        producer_available: bool,
        plan: dict[str, Any],
        intel: dict[str, Any],
        settings: dict[str, Any],
    ):
        """Keep the runtime-layer boundary stable while delegating pure evaluation."""
        # Safety invariant is enforced by the evaluator:
        # row.get("planning_input_ready") is True for participating flexible demand.
        return evaluate_runtime_layers(
            self.model, self.store.data.get("metering") or {}, facts, flexible,
            logical_assets, producer_available, plan, intel, settings,
        )
    @staticmethod
    def _battery_units(logical_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for asset in logical_assets:
            if asset.get("object_class") != "battery":
                continue
            props = {str(row.get("property_key")): row for row in (asset.get("properties") or []) if isinstance(row, dict) and row.get("property_key")}
            rows.append({
                "asset_id": asset.get("asset_id"),
                "display_name": asset.get("display_name"),
                "integration_domain": asset.get("integration_domain"),
                "power_kw": (props.get("battery.power_kw") or {}).get("value"),
                "soc_pct": (props.get("battery.soc_pct") or {}).get("value"),
                "capacity_kwh": (props.get("battery.capacity_kwh") or {}).get("value"),
                "available_kwh": (props.get("battery.available_kwh") or {}).get("value"),
                "status": (props.get("battery.status") or {}).get("value"),
                "health": asset.get("health"),
            })
        return rows
    def configure_emhass_shadow(self, url: str, options: dict[str, Any]) -> None:
        """Enable bounded solver qualification; deterministic planning stays primary."""
        from .emhass_shadow import EmhassShadowRunner
        self._emhass_runner = EmhassShadowRunner(
            self.hass, url=url, options=options,
            notify=self._publish_emhass_shadow_status,
        )
        if self.model is not None:
            self.planning_cadence.request_refresh()
            self._recompute()

    def _publish_emhass_shadow_status(self) -> None:
        """Publish result evidence without recomputing telemetry or planner."""
        if self._emhass_stopping or self._emhass_runner is None:
            return
        self.snapshot.setdefault("planning_providers", {})["emhass"] = dict(self._emhass_runner.status)
        self._notify(public_changed=True)

    def _schedule_emhass_shadow(self, facts, logical_assets, flexible, settings) -> None:
        if self._emhass_runner is None:
            return
        self._emhass_runner.request(
            model=self.model, facts=dict(facts),
            batteries=self._battery_units(logical_assets), loads=flexible,
            metering_profile=(self.store.data.get("metering") or {}).get("baseload_profile") or {},
            strategy=settings.get("strategy") or {},
            cadence_revision=self.planning_cadence.diagnostics().get("last_tactical_refresh_at"),
        )
        self.snapshot["planning_providers"]["emhass"] = dict(self._emhass_runner.status)

    def start_emhass_probe(self, url: str) -> None:
        """Schedule a single HA-managed connection probe, owned by this runtime."""
        if self._emhass_stopping or (self._emhass_probe_task and not self._emhass_probe_task.done()):
            return
        self._emhass_probe_task = self.hass.async_create_task(
            self.async_probe_emhass(url)
        )

    async def async_probe_emhass(self, url: str) -> None:
        """Read-only connection probe; never equate connectivity with solver readiness."""
        from .emhass_client import VanillaEmhassClient

        self._emhass_connection = {
            "status": "CONNECTING", "readiness": "UNVALIDATED",
            "selected": False, "mode": "shadow",
            "result_status": "UNAVAILABLE",
        }
        try:
            config = await VanillaEmhassClient(self.hass, url).probe()
            if not isinstance(config, dict):
                raise ValueError("invalid_emhass_config_response")
            self._emhass_connection.update({
                "status": "CONNECTED", "readiness": "INPUTS_NOT_VALIDATED",
                "result_status": "UNAVAILABLE",
                "last_error": None,
            })
        except Exception as exc:
            self._emhass_connection.update({
                "status": "CONNECTION_FAILED", "readiness": "UNAVAILABLE",
                "last_error": type(exc).__name__,
            })
        if self._emhass_stopping:
            return
        self.snapshot.setdefault("planning_providers", {})["emhass"] = dict(self._emhass_connection)
        self._notify(public_changed=True)

