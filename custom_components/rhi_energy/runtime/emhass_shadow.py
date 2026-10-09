"""Async, bounded EMHASS shadow optimization over accepted Energy source evidence.

Only RHI Energy owns orchestration and results. This runner never publishes to
Home Assistant EMHASS sensors and never issues physical commands.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any

from .emhass_client import VanillaEmhassClient
from .emhass_context import build_emhass_context
from .emhass_result_adapter import accept_shadow_plan

_NATIVE_KEYS = frozenset({
    "set_use_battery", "number_of_batteries", "battery_nominal_energy_capacity",
    "battery_charge_power_max", "battery_discharge_power_max",
    "battery_minimum_state_of_charge", "battery_maximum_state_of_charge",
    "battery_charge_efficiency", "battery_discharge_efficiency",
    "soc_init", "soc_final", "number_of_deferrable_loads",
    "nominal_power_of_deferrable_loads", "minimum_power_of_deferrable_loads",
    "operating_hours_of_each_deferrable_load", "start_timesteps_of_each_deferrable_load",
    "end_timesteps_of_each_deferrable_load", "maximum_power_from_grid",
    "maximum_power_to_grid", "prediction_horizon",
})


def selected_solar_forecast_entry(model: dict[str, Any] | None) -> str:
    """Resolve exact selected source, never scan HA or infer from entity names."""
    matches = set()
    for row in (model or {}).get("accepted_bindings") or []:
        if not isinstance(row, dict):
            continue
        concept = str(row.get("object_class") or row.get("concept_id") or row.get("object_type") or "")
        cap = row.get("technical_capability") or {}
        source = row.get("source_identity") or {}
        domain = str(source.get("integration_domain") or "")
        if domain != "forecast_solar" or (concept and concept != "solar_forecast"):
            continue
        entry = source.get("config_entry_id") or (row.get("config_entry_relation") or {}).get("config_entry_id")
        if entry:
            matches.add(str(entry))
    if len(matches) != 1:
        raise ValueError("selected_solar_forecast_entry_missing_or_ambiguous")
    return next(iter(matches))


async def hourly_pv_from_accepted_forecast(hass: Any, config_entry_id: str) -> dict[str, float]:
    if not hass.services.has_service("forecast_solar", "get_forecast"):
        raise ValueError("forecast_solar_hourly_service_unavailable")
    result = await hass.services.async_call(
        "forecast_solar", "get_forecast",
        {"config_entry": config_entry_id, "resolution": "hourly"},
        blocking=True, return_response=True,
    )
    if not isinstance(result, dict) or not isinstance(result.get("watts"), dict):
        raise ValueError("hourly_pv_response_missing")
    return result["watts"]


class EmhassShadowRunner:
    def __init__(self, hass: Any, *, url: str, options: dict[str, Any], notify):
        self.hass = hass
        self.url = url
        self.options = dict(options)
        self.notify = notify
        self._task: asyncio.Task | None = None
        self._generation = 0
        self._stopped = False
        self.status: dict[str, Any] = {
            "status": "CONFIGURED", "mode": "shadow", "selected": False,
            "readiness": "INPUTS_NOT_VALIDATED", "result_status": "UNAVAILABLE",
        }
        self.result = None

    def request(self, *, model: dict[str, Any] | None, facts: dict[str, Any],
                batteries: list[dict[str, Any]], loads: list[dict[str, Any]],
                metering_profile: dict[str, Any], strategy: dict[str, Any],
                cadence_revision: Any) -> None:
        if self._stopped or (self._task is not None and not self._task.done()):
            return
        if cadence_revision is None or cadence_revision == self.status.get("requested_cadence_revision"):
            return
        self._generation += 1
        generation = self._generation
        self.status["requested_cadence_revision"] = cadence_revision
        self.status.update(status="OPTIMIZING", result_status="PENDING")
        self._task = self.hass.async_create_task(self._run(
            generation, model, dict(facts), [dict(row) for row in batteries],
            [dict(row) for row in loads], dict(metering_profile), dict(strategy),
        ))

    async def _run(self, generation, model, facts, batteries, loads, metering_profile, strategy):
        try:
            requested_hours = self.options.get("emhass_horizon_hours", 24)
            if requested_hours not in (24, 48):
                raise ValueError("unsupported_emhass_horizon")
            # Solver configuration is an external contract. Do not silently use
            # 30-minute steps with hourly inputs.
            client = VanillaEmhassClient(self.hass, self.url)
            config = await client.probe()
            if not isinstance(config, dict):
                raise ValueError("emhass_configuration_invalid")
            version = str(config.get("emhass_version") or config.get("version") or "")
            if version and version != "0.18.5":
                raise ValueError("incompatible_emhass_version:" + version)
            optimization = config.get("optimization_time_step")
            if optimization is None:
                for container_key in ("config", "params", "retrieve_hass_conf"):
                    nested = config.get(container_key)
                    if isinstance(nested, dict) and "optimization_time_step" in nested:
                        optimization = nested["optimization_time_step"]
                        break
            if optimization is None or float(optimization) != 60:
                raise ValueError("emhass_optimization_step_not_verified_60_minutes")
            pv_source = selected_solar_forecast_entry(model)
            pv = await hourly_pv_from_accepted_forecast(self.hass, pv_source)
            start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            if start < datetime.now(timezone.utc):
                from datetime import timedelta
                start += timedelta(hours=1)
            context = build_emhass_context(
                start_utc=start, horizon_hours=requested_hours,
                local_timezone=self.hass.config.time_zone,
                pv_watts=pv,
                import_price_intervals=facts.get("pricing.future_prices"),
                currency=str(facts.get("pricing.currency") or ""),
                export_price_eur_kwh=self.options.get("emhass_export_price_eur_kwh"),
                baseload_profile=metering_profile, battery_units=batteries,
                battery_configuration=self.options.get("emhass_battery_configuration") or {},
                flexible_assets=loads,
                grid_import_limit_kw=self.options.get("emhass_grid_import_limit_kw"),
                grid_export_limit_kw=self.options.get("emhass_grid_export_limit_kw"),
                reserve_target_pct=strategy.get("battery.reserve_target_pct"),
                supported_native_parameters=set(_NATIVE_KEYS),
            )
            run = await client.optimize_shadow(context.payload, action="naive-mpc-optim")
            accepted = accept_shadow_plan(run.plan, run.last_run, context)
            runtime_version = str(run.last_run.get("emhass_version") or version or "")
            if runtime_version and runtime_version != "0.18.5":
                raise ValueError("native_optimizer_version_mismatch:" + runtime_version)
            version_verified = runtime_version == "0.18.5"
            if self._stopped or generation != self._generation:
                return
            self.result = accepted
            self.status.update({
                "status": "SHADOW_PLAN_ACCEPTED" if version_verified else "SHADOW_VERSION_UNVERIFIED",
                "readiness": "SHADOW_VALIDATED" if version_verified else "VERSION_UNVERIFIED",
                "version_verified": version_verified, "emhass_version": runtime_version or None,
                "result_status": "ACCEPTED_READ_ONLY", "reason": None,
                "generated_at": accepted.generated_at,
                "battery_count": len(accepted.battery_ids),
                "flexible_load_count": len(accepted.flexible_ids),
                "planned_import_kwh": accepted.total_import_kwh,
                "planned_export_kwh": accepted.total_export_kwh,
                "net_financial_result_eur": accepted.net_financial_result_eur,
                "flexible_scheduled_kwh": accepted.flexible_scheduled_kwh,
            })
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._stopped or generation != self._generation:
                return
            self.result = None
            self.status.update({
                "status": "SHADOW_BLOCKED", "readiness": "UNAVAILABLE",
                "result_status": "REJECTED",
                "reason": f"{type(exc).__name__}:{str(exc)[:200]}",
            })
        if not self._stopped and generation == self._generation:
            self.notify()

    async def async_stop(self):
        self._stopped = True
        self._generation += 1
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
