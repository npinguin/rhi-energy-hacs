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
                "max_charge_power_kw": (props.get("battery.max_charge_power_kw") or {}).get("value"),
                "max_discharge_power_kw": (props.get("battery.max_discharge_power_kw") or {}).get("value"),
                "charge_limit_kw": (props.get("battery.charge_limit_kw") or {}).get("value"),
                "discharge_limit_kw": (props.get("battery.discharge_limit_kw") or {}).get("value"),
                "reserve_soc_pct": (props.get("battery.reserve_soc_pct") or {}).get("value"),
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

    def _select_effective_planner(self, deterministic, settings):
        """Select a validated provider without permitting EMHASS command ownership."""
        from datetime import datetime, timezone
        from .canonical_semantics import automation_control_policy
        from .emhass_advisory import project_emhass_advisory, AdvisoryProjectionError
        from .planner_selection import select_plan, FallbackPolicy

        runner = self._emhass_runner
        requested = str(
            (runner.options.get("planner_provider") if runner else None)
            or getattr(self, "_selected_planner_provider", "rhi_deterministic")
        )
        if requested != "emhass":
            return deterministic, {
                "requested_provider": "rhi_deterministic",
                "effective_provider": "rhi_deterministic",
                "reason": "default_deterministic_primary",
            }

        valid_rhi = deterministic.get("health") == "OK"
        native = None
        native_valid = False
        reject_reason = "native_optimizer_not_available"
        if runner is not None and runner.result is not None:
            status = runner.status
            active_revision = self.planning_cadence.diagnostics().get("last_tactical_refresh_at")
            version_ok = status.get("version_verified") is True
            current_revision = status.get("requested_cadence_revision") == active_revision
            if status.get("status") == "SHADOW_PLAN_ACCEPTED" and version_ok and current_revision:
                try:
                    native = project_emhass_advisory(
                        runner.result,
                        time_zone=str(self.hass.config.time_zone),
                        now=datetime.now(timezone.utc),
                    )
                    native_valid = True
                except (AdvisoryProjectionError, ValueError) as exc:
                    reject_reason = f"native_projection_rejected:{type(exc).__name__}"
            else:
                reject_reason = "native_version_or_generation_not_validated"
        # Never silently switch a user-selected native Automatic controller to
        # a different physical planner. Advisory fallback is permitted; an
        # automatic run requires explicit provider authority and otherwise HOLD.
        fallback = (
            FallbackPolicy.HOLD
            if automation_control_policy(settings)["autonomous_execution_allowed"]
            else FallbackPolicy.RHI
        )
        decision = select_plan(
            "emhass",
            {"rhi_deterministic": deterministic, **({"emhass": native} if native is not None else {})},
            {"rhi_deterministic": valid_rhi, "emhass": native_valid},
            fallback=fallback,
        )
        effective = decision.plan
        if effective is None:
            # An unavailable plan is not replaced by a fabricated empty schedule.
            return {"health": "UNAVAILABLE", "reason": "no_validated_plan_hold",
                    "planning_horizons": {}, "planning_horizons_json": [],
                    "execution_authorized": False,
                    "execution_policy": automation_control_policy(settings)}, {
                "requested_provider": "emhass",
                "effective_provider": None,
                "reason": reject_reason,
            }
        if decision.effective_provider == "emhass":
            effective["execution_policy"] = automation_control_policy(settings)
            effective["execution_authorized"] = False
        return effective, {
            "requested_provider": "emhass",
            "effective_provider": decision.effective_provider,
            "reason": decision.reason if native_valid else reject_reason,
        }

    def _publish_emhass_shadow_status(self) -> None:
        """Publish result evidence without recomputing telemetry or planner."""
        if self._emhass_stopping or self._emhass_runner is None:
            return
        # Solver results may change the effective advisory provider; re-evaluate
        # against the unchanged tactical revision before publishing the snapshot.
        self._recompute()

    def _schedule_emhass_shadow(self, facts, logical_assets, flexible, settings) -> None:
        if self._emhass_runner is None:
            return
        self._emhass_runner.request(
            model=self.model, facts=dict(facts),
            batteries=self._battery_units(logical_assets), loads=flexible,
            metering_profile=(self.store.data.get("metering") or {}).get("baseload_profile") or {},
            strategy=settings.get("strategy") or {},
            settings=settings,
            cadence_revision=self.planning_cadence.diagnostics().get("last_tactical_refresh_at"),
        )
        self.snapshot["planning_providers"]["emhass"] = {
            **dict(self._emhass_runner.status),
            "selected": (self.snapshot.get("planning_selection") or {}).get("effective_provider") == "emhass",
        }

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

