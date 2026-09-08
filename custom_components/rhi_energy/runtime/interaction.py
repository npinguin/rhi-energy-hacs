"""Energy public interaction engine.

Energy persists command admission before any physical dispatch. Producer domains remain
owners of physical execution; Energy only invokes exact producer-published command
references and marks a command CONFIRMED after authoritative readback. Repeated calls
share a durable fingerprint within the idempotency window so reloads/retries cannot
blindly duplicate a physical operation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from ..compat_core import (
    AVAILABLE,
    PENDING,
    UNSUPPORTED,
    automatic_execution_decision,
    by_key,
    command_state_key,
    number,
    protective_execution_decision,
    strategy_properties,
)
from ..const import COMMAND_IDEMPOTENCY_WINDOW_SECONDS, COMMAND_TIMEOUT_SECONDS
from .producers import resolve_mobility_command

_LOGGER = logging.getLogger(__name__)
_TERMINAL = {"CONFIRMED", "REJECTED", "TIMED_OUT"}


class EnergyInteractionEngine:
    def __init__(self, hass: HomeAssistant, store: Any, runtime: Any, metering: Any, manager: Any) -> None:
        self.hass = hass
        self.store = store
        self.runtime = runtime
        self.metering = metering
        self.manager = manager
        self._callbacks = []
        self._remove_runtime = None
        self._remove_timer = None
        self._last_auto: dict[str, datetime] = {}

    def add_callback(self, cb):
        self._callbacks.append(cb)
        return lambda: self._callbacks.remove(cb) if cb in self._callbacks else None

    def _notify(self) -> None:
        for cb in tuple(self._callbacks):
            cb()

    async def async_start(self) -> None:
        self._remove_runtime = self.runtime.add_callback(self.reconcile)
        self._remove_timer = async_track_time_interval(self.hass, self._automatic_tick, timedelta(minutes=1))
        self.reconcile()

    def _find_asset(self, asset_id: str) -> dict[str, Any] | None:
        return next(
            (a for a in self.runtime.snapshot.get("flexible_assets", []) if a.get("asset_id") == asset_id),
            None,
        )

    @staticmethod
    def _row_ready(row: dict[str, Any]) -> bool:
        if row.get("supported") is False:
            return False
        if row.get("manual_execution_ready") is True or row.get("public_execution_allowed") is True:
            return True
        state = str(row.get("state") or row.get("availability") or row.get("readiness") or "").upper()
        return state in {"AVAILABLE", "READY", "TRUE", "ON"}

    def _resolve_producer(self, target: str, role: str) -> dict[str, Any] | None:
        """Resolve only the exact Mobility command reference published for the asset."""
        asset = self._find_asset(target)
        if not asset or str(asset.get("source_domain") or "mobility") != "mobility":
            return None
        return resolve_mobility_command(self.hass, asset, role)

    @staticmethod
    def _fingerprint(command_id: str, target: str, period_id: str | None, parameters: dict[str, Any]) -> str:
        payload = {
            "command_id": command_id,
            "target": target,
            "period_id": period_id,
            "parameters": parameters,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()[:20]

    @staticmethod
    def _same_operation(existing: dict[str, Any], fingerprint: str, now: datetime) -> bool:
        if existing.get("fingerprint") != fingerprint:
            return False
        if existing.get("status") == PENDING:
            return True
        if existing.get("status") not in _TERMINAL:
            return False
        timestamp = existing.get("completed_at") or existing.get("requested_at")
        try:
            at = datetime.fromisoformat(str(timestamp))
            if at.tzinfo is None:
                at = at.replace(tzinfo=now.tzinfo)
            return (now - at).total_seconds() <= COMMAND_IDEMPOTENCY_WINDOW_SECONDS
        except (TypeError, ValueError):
            return True

    async def _dispatch_producer(
        self,
        target: str,
        role: str,
        parameters: dict[str, Any],
    ) -> tuple[bool, str, str | None]:
        row = self._resolve_producer(target, role)
        if row is None:
            return False, "producer_command_not_published", None
        if not self._row_ready(row):
            return (
                False,
                str(row.get("manual_blocked_reason") or row.get("reason") or "producer_command_not_ready"),
                "mobility",
            )
        invoke = row.get("invoke") if isinstance(row.get("invoke"), dict) else {}
        service = invoke.get("service") or row.get("service")
        data = deepcopy(
            invoke.get("data")
            if isinstance(invoke.get("data"), dict)
            else row.get("data")
            if isinstance(row.get("data"), dict)
            else {}
        )
        if not service or "." not in str(service):
            return False, "producer_invoke_reference_missing", "mobility"
        parameter_map = invoke.get("parameter_map") if isinstance(invoke.get("parameter_map"), dict) else {}
        for key, value in parameters.items():
            if value is None:
                continue
            data[str(parameter_map.get(key) or key)] = value
        domain, service_name = str(service).split(".", 1)
        await self.hass.services.async_call(domain, service_name, data, blocking=False)
        return True, "dispatched_via_mobility_contract", "mobility"

    def _selected_energy_provider(self, concept: str) -> dict[str, Any] | None:
        providers = (((self.manager.compiled_model or {}).get("concepts") or {}).get(concept) or {}).get("providers") or []
        providers = [row for row in providers if isinstance(row, dict)]
        if len(providers) == 1:
            return providers[0]
        preferred = (((self.store.data.get("settings") or {}).get("sources") or {}).get(concept))
        if preferred in {None, "", "auto"}:
            return None
        wanted = str(preferred)
        matches = [
            row for row in providers
            if wanted in {str(row.get("asset_id") or ""), str(row.get("integration_domain") or ""), str(row.get("builder_id") or "")}
        ]
        return matches[0] if len(matches) == 1 else None

    async def write_property(self, property_id: str, value: Any) -> dict[str, Any]:
        settings = self.store.data.setdefault("settings", {})
        pricing = settings.setdefault("pricing", {})
        strategy = settings.setdefault("strategy", {})
        result = {
            "property_id": property_id,
            "requested_value": value,
            "status": "REJECTED",
            "reason": "unsupported_property",
        }
        pricing_map = {
            "pricing.spot_eur_kwh": "spot_fallback_eur_kwh",
            "pricing.import_network_eur_kwh": "import_network_eur_kwh",
            "pricing.import_levies_eur_kwh": "import_levies_eur_kwh",
            "pricing.import_vat_pct": "import_vat_pct",
            "pricing.export_fee_eur_kwh": "export_fee_eur_kwh",
        }
        if property_id in pricing_map:
            numeric = number(value)
            if numeric is None:
                result["reason"] = "invalid_number"
            else:
                pricing[pricing_map[property_id]] = numeric
                result.update(status="CONFIRMED", reason="persisted_pricing_intent", readback_value=numeric)
        elif property_id in {r["property_id"] for r in strategy_properties({"strategy": strategy})}:
            rows = by_key(strategy_properties({"strategy": strategy}))
            row = rows[property_id]
            if property_id == "battery.reserve_target_pct":
                numeric = number(value)
                constraints = row.get("constraints") or {}
                if numeric is None or numeric < float(constraints.get("min", 5)) or numeric > float(constraints.get("max", 80)):
                    result["reason"] = "outside_constraints"
                else:
                    strategy[property_id] = numeric
                    result.update(status="CONFIRMED", reason="persisted_strategy_intent", readback_value=numeric)
            else:
                normalized = str(value).lower()
                if property_id in {"energy.automation_mode", "energy.operating_mode"}:
                    normalized = {"off": "disabled", "recommend": "advice"}.get(normalized, normalized)
                allowed = (row.get("constraints") or {}).get("allowed") or []
                if allowed and normalized not in allowed:
                    result["reason"] = "outside_constraints"
                else:
                    strategy[property_id] = normalized
                    if property_id in {"energy.automation_mode", "energy.operating_mode"}:
                        strategy["energy.automation_mode"] = normalized
                        strategy["energy.operating_mode"] = normalized
                    result.update(status="CONFIRMED", reason="persisted_strategy_intent", readback_value=normalized)
        elif property_id in {"metering.selected_period_id", "metering.selected_period"}:
            normalized = str(value).lower()
            if normalized not in {"today", "week", "month", "year"}:
                result["reason"] = "invalid_period"
            else:
                settings["metering_selected_period"] = normalized
                result.update(status="CONFIRMED", reason="persisted_metering_context", readback_value=normalized)
        elif property_id.endswith(".requested_power_kw"):
            asset_id = property_id[: -len(".requested_power_kw")]
            numeric = number(value)
            asset = self._find_asset(asset_id)
            if numeric is None or asset is None:
                result["reason"] = "asset_or_value_invalid"
            elif asset.get("min_power_kw") is not None and numeric > 0 and numeric < float(asset["min_power_kw"]):
                result["reason"] = "below_min_power"
            elif asset.get("max_power_kw") is not None and numeric > float(asset["max_power_kw"]):
                result["reason"] = "above_max_power"
            else:
                command = await self.invoke_command(
                    "energy.command.set_flexible_load_power",
                    asset_id,
                    {"requested_power_kw": numeric},
                )
                result.update(
                    status=command.get("status"),
                    reason=command.get("reason"),
                    readback_value=(self._find_asset(asset_id) or {}).get("requested_power_kw"),
                )
        elif property_id == "battery.reserve_soc_pct":
            model = self.manager.compiled_model or {}
            provider = self._selected_energy_provider("battery_system")
            reserve = (provider or {}).get("reserve_binding")
            binding = next(
                (b for b in model.get("accepted_bindings", []) if b.get("binding_id") == reserve),
                None,
            )
            entity_id = (binding or {}).get("source_identity", {}).get("current_entity_id")
            numeric = number(value)
            if not entity_id or not str(entity_id).startswith("number."):
                result["reason"] = "physical_reserve_write_unsupported"
            elif numeric is None or not 0 <= numeric <= 100:
                result["reason"] = "invalid_number"
            else:
                await self.hass.services.async_call(
                    "number", "set_value", {"entity_id": entity_id, "value": numeric}, blocking=True
                )
                readback = self.hass.states.get(entity_id)
                actual = number(readback.state) if readback else None
                confirmed = actual is not None and abs(actual - numeric) <= 0.51
                result.update(
                    status="CONFIRMED" if confirmed else PENDING,
                    reason=(
                        "authoritative_physical_readback_confirmed"
                        if confirmed
                        else "physical_write_dispatched_awaiting_readback"
                    ),
                    readback_value=actual,
                )
        self.store.add_activity(
            {
                "activity_type": "property_write",
                "property_id": property_id,
                "status": result["status"],
                "reason": result["reason"],
            }
        )
        await self.store.async_save()
        self.runtime._recompute()
        self._notify()
        return result

    async def _admit(
        self,
        command_id: str,
        target: str,
        period_id: str | None,
        parameters: dict[str, Any],
    ) -> tuple[str, dict[str, Any], bool]:
        key = command_state_key(command_id, target, period_id)
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        fingerprint = self._fingerprint(command_id, target, period_id, parameters)
        existing = (self.store.data.get("command_state") or {}).get(key) or {}
        if self._same_operation(existing, fingerprint, now):
            return key, deepcopy(existing), False
        row = {
            "operation_id": f"energy:{fingerprint}:{int(now.timestamp() * 1000)}",
            "idempotency_key": fingerprint,
            "fingerprint": fingerprint,
            "command_id": command_id,
            "target_asset_id": target,
            "period_id": period_id,
            "requested_at": now.isoformat(),
            "deadline_at": (now + timedelta(seconds=COMMAND_TIMEOUT_SECONDS)).isoformat(),
            "status": PENDING,
            "dispatch_state": "ADMITTED",
            "reason": "admitted_pending_dispatch",
            "parameters": deepcopy(parameters),
        }
        self.store.data.setdefault("command_state", {})[key] = row
        await self.store.async_save()  # durable admission precedes any external side effect
        return key, row, True

    async def invoke_command(
        self,
        command_id: str,
        target_asset_id: str | None = None,
        parameters: dict[str, Any] | None = None,
        period_id: str | None = None,
    ) -> dict[str, Any]:
        parameters = parameters or {}
        target = target_asset_id or ""
        normalized_period = period_id
        if command_id == "energy.command.reset_metering_baseline":
            normalized_period = period_id or str(parameters.get("period_id") or "")
            target = "metering"
        key, row, newly_admitted = await self._admit(command_id, target, normalized_period, parameters)
        if not newly_admitted:
            return row

        try:
            if command_id == "energy.command.reset_metering_baseline":
                ok = await self.metering.reset_period(str(normalized_period or ""))
                row.update(
                    period_id=normalized_period,
                    status="CONFIRMED" if ok else "REJECTED",
                    dispatch_state="LOCAL_COMPLETE",
                    reason="metering_baseline_reset_confirmed" if ok else "invalid_period",
                )
            elif command_id in {"energy.command.pause_flexible_load", "energy.command.resume_flexible_load"}:
                holds = self.store.data.setdefault("settings", {}).setdefault("holds", {})
                if not self._find_asset(target):
                    row.update(status="REJECTED", reason="target_asset_unavailable", dispatch_state="NOT_DISPATCHED")
                elif command_id.endswith("pause_flexible_load"):
                    holds[target] = True
                    # Hold is authoritative Energy intent and is already durable before
                    # the optional producer stop is attempted.
                    await self.store.async_save()
                    ok, reason, producer = await self._dispatch_producer(target, "stop", {})
                    row.update(
                        status=PENDING if ok else "CONFIRMED",
                        dispatch_state="DISPATCHED" if ok else "LOCAL_COMPLETE",
                        reason=reason if ok else "planning_hold_enabled",
                        expected_state="idle" if ok else None,
                        producer_domain=producer,
                    )
                else:
                    holds.pop(target, None)
                    row.update(status="CONFIRMED", dispatch_state="LOCAL_COMPLETE", reason="planning_hold_cleared")
            elif command_id in {
                "energy.command.start_flexible_load",
                "energy.command.stop_flexible_load",
                "energy.command.set_flexible_load_power",
            }:
                role = "start" if "start" in command_id else "stop" if "stop" in command_id else "adjust"
                payload: dict[str, Any] = {}
                if role == "adjust":
                    payload = {
                        "requested_power_kw": number(
                            parameters.get("requested_power_kw")
                            if "requested_power_kw" in parameters
                            else parameters.get("value")
                        )
                    }
                if role == "adjust" and payload["requested_power_kw"] is None:
                    row.update(status="REJECTED", dispatch_state="NOT_DISPATCHED", reason="invalid_requested_power")
                else:
                    ok, reason, producer = await self._dispatch_producer(target, role, payload)
                    row.update(
                        status=PENDING if ok else "REJECTED",
                        dispatch_state="DISPATCHED" if ok else "NOT_DISPATCHED",
                        reason=reason,
                        producer_domain=producer,
                        expected_state="running" if role == "start" else "idle" if role == "stop" else None,
                        expected_requested_power_kw=payload.get("requested_power_kw"),
                    )
            elif command_id == "energy.command.execute_plan":
                await self._execute_plan("manual")
                row.update(status="CONFIRMED", dispatch_state="LOCAL_COMPLETE", reason="plan_evaluated")
            else:
                row.update(status="REJECTED", dispatch_state="NOT_DISPATCHED", reason="unsupported_command")
        except Exception as exc:  # persist terminal failure; never lose an admitted operation
            row.update(
                status="REJECTED",
                dispatch_state="DISPATCH_FAILED",
                reason=f"producer_dispatch_exception:{type(exc).__name__}",
            )
            _LOGGER.exception("Energy command dispatch failed command=%s target=%s", command_id, target)

        if row.get("status") in _TERMINAL:
            row["completed_at"] = datetime.now(ZoneInfo(self.hass.config.time_zone)).isoformat()
        self.store.data.setdefault("command_state", {})[key] = row
        self.store.add_activity(
            {
                "activity_type": "command",
                "command_id": command_id,
                "target_asset_id": row.get("target_asset_id"),
                "status": row["status"],
                "reason": row["reason"],
            }
        )
        await self.store.async_save()
        if row.get("status") == "REJECTED":
            _LOGGER.warning(
                "Energy command rejected: command=%s target=%s reason=%s",
                command_id,
                row.get("target_asset_id"),
                row.get("reason"),
            )
        self._notify()
        return deepcopy(row)

    def reconcile(self) -> None:
        changed = False
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        for row in (self.store.data.get("command_state") or {}).values():
            if row.get("status") != PENDING:
                continue
            deadline = row.get("deadline_at")
            try:
                expired = bool(deadline and now >= datetime.fromisoformat(str(deadline)))
            except (TypeError, ValueError):
                expired = False
            if expired:
                row.update(
                    status="TIMED_OUT",
                    reason="authoritative_readback_timeout",
                    completed_at=now.isoformat(),
                )
                changed = True
                continue
            asset = self._find_asset(str(row.get("target_asset_id") or ""))
            if not asset:
                continue
            expected = row.get("expected_state")
            if expected:
                operating = str(asset.get("operating_state") or "").lower()
                ok = (expected == "running" and operating in {"running", "charging", "active", "on"}) or (
                    expected == "idle" and operating in {"idle", "stopped", "paused", "off", "disconnected"}
                )
                if ok:
                    row.update(
                        status="CONFIRMED",
                        reason="authoritative_physical_readback_confirmed",
                        completed_at=now.isoformat(),
                    )
                    changed = True
            elif row.get("expected_requested_power_kw") is not None:
                readback = number(asset.get("requested_power_kw"))
                expected_power = number(row.get("expected_requested_power_kw"))
                if readback is not None and expected_power is not None and abs(readback - expected_power) <= 0.11:
                    row.update(
                        status="CONFIRMED",
                        reason="authoritative_requested_power_readback_confirmed",
                        completed_at=now.isoformat(),
                    )
                    changed = True
        if changed:
            self.hass.async_create_task(self.store.async_save())
            self._notify()

    def command_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        states = self.store.data.get("command_state") or {}
        for asset in self.runtime.snapshot.get("flexible_assets", []):
            asset_id = asset["asset_id"]
            for command_id, role in (
                ("energy.command.start_flexible_load", "start"),
                ("energy.command.stop_flexible_load", "stop"),
                ("energy.command.set_flexible_load_power", "adjust"),
                ("energy.command.pause_flexible_load", "pause"),
                ("energy.command.resume_flexible_load", "resume"),
            ):
                producer = self._resolve_producer(
                    asset_id,
                    role if role in {"start", "stop", "adjust"} else "stop",
                ) if role != "resume" else None
                supported = role in {"pause", "resume"} or producer is not None
                ready = role in {"pause", "resume"} or (producer is not None and self._row_ready(producer))
                key = command_state_key(command_id, asset_id)
                last = states.get(key, {})
                rows.append(
                    {
                        "command_instance_id": f"{command_id}.{asset_id}",
                        "command_id": command_id,
                        "owner": "energy",
                        "target_asset_id": asset_id,
                        "role": role,
                        "supported": supported,
                        "availability": AVAILABLE if ready else (UNSUPPORTED if producer is None and role not in {"pause", "resume"} else "UNAVAILABLE"),
                        "state": "available" if ready else "unavailable",
                        "reason": {
                            "code": None if ready else "producer_command_unavailable",
                            "message": None if ready else "Physical command is not currently published/ready by the producer domain.",
                            "severity": None if ready else "blocking",
                            "source": "producer_contract",
                        },
                        "producer_domain": "mobility" if producer is not None else asset.get("source_domain"),
                        "parameters": {
                            "requested_power_kw": {
                                "required": True,
                                "min": asset.get("min_power_kw"),
                                "max": asset.get("max_power_kw"),
                                "unit": "kW",
                            }
                        }
                        if role == "adjust"
                        else {},
                        "requires_confirmation": role in {"start", "stop"},
                        "invoke": {
                            "operation_id": "energy.command.execute",
                            "service": "script.energy_execute_public_command",
                            "data": {"command_id": command_id, "target_asset_id": asset_id, "parameters": {}},
                        },
                        "readback": {
                            "command_instance_id": f"{command_id}.{asset_id}",
                            "state": str(last.get("status") or "IDLE").lower(),
                            "result_code": last.get("reason"),
                            "feedback_confirmed": last.get("status") == "CONFIRMED",
                        },
                        "execution_status": last.get("status") or "IDLE",
                        "authoritative_readback_index": "sensor.energy_flexible_asset_index",
                    }
                )
        for period in ("today", "week", "month", "year"):
            command_id = "energy.command.reset_metering_baseline"
            key = command_state_key(command_id, "metering", period)
            last = states.get(key, {})
            rows.append(
                {
                    "command_instance_id": f"{command_id}.{period}.metering",
                    "command_id": command_id,
                    "owner": "energy",
                    "target_asset_id": "metering",
                    "period_id": period,
                    "role": "reset_baseline",
                    "supported": True,
                    "availability": AVAILABLE,
                    "state": "available",
                    "reason": {"code": None, "message": None, "severity": None, "source": "metering"},
                    "parameters": {"period_id": {"value": period, "required": True, "allowed": ["today", "week", "month", "year"]}},
                    "requires_confirmation": True,
                    "invoke": {
                        "operation_id": "energy.command.execute",
                        "service": "script.energy_execute_public_command",
                        "data": {"command_id": command_id, "target_asset_id": "metering", "period_id": period, "parameters": {}},
                    },
                    "readback": {
                        "command_instance_id": f"{command_id}.{period}.metering",
                        "state": str(last.get("status") or "IDLE").lower(),
                        "result_code": last.get("reason"),
                        "feedback_confirmed": last.get("status") == "CONFIRMED",
                    },
                    "execution_status": last.get("status") or "IDLE",
                    "authoritative_readback_index": "sensor.energy_metering_property_index",
                }
            )
        rows.append(
            {
                "command_instance_id": "energy.command.execute_plan.energy",
                "command_id": "energy.command.execute_plan",
                "owner": "energy",
                "target_asset_id": "energy",
                "role": "execute_plan",
                "supported": True,
                "availability": AVAILABLE,
                "state": "available",
                "reason": {"code": None, "message": None, "severity": None, "source": "energy"},
                "parameters": {},
                "requires_confirmation": False,
                "invoke": {
                    "operation_id": "energy.command.execute",
                    "service": "script.energy_execute_public_command",
                    "data": {"command_id": "energy.command.execute_plan", "target_asset_id": "energy", "parameters": {}},
                },
                "readback": {"state": "idle", "feedback_confirmed": True},
                "execution_status": "IDLE",
                "authoritative_readback_index": "sensor.energy_planning_index",
            }
        )
        return rows

    async def _automatic_tick(self, _now) -> None:
        strategy = (self.store.data.get("settings") or {}).get("strategy", {})
        mode = strategy.get("energy.automation_mode") or strategy.get("energy.operating_mode")
        if mode != "automatic":
            return
        await self._execute_plan("automatic")

    async def _execute_plan(self, origin: str) -> None:
        snap = self.runtime.snapshot
        facts = snap.get("facts") or {}
        export_kw = facts.get("grid_export.power_kw")
        holds = (self.store.data.get("settings") or {}).get("holds", {})
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        assets = list(snap.get("flexible_assets", []))

        # Negative safety guard has precedence and may only reduce/stop.
        for asset in assets:
            asset_id = str(asset["asset_id"])
            decision = protective_execution_decision(
                facts.get("grid_import.power_kw"),
                facts.get("battery.power_kw"),
                asset,
            )
            if decision["action"] == "stop":
                result = await self.invoke_command("energy.command.stop_flexible_load", asset_id, {})
                if result.get("status") in {PENDING, "CONFIRMED"}:
                    self._last_auto[asset_id] = now

        # At most one positive handoff per evaluation. Requested-power readback must be
        # CONFIRMED before the producer start command is admitted; PENDING is never
        # treated as proof that the requested power was applied.
        for asset in assets:
            asset_id = str(asset["asset_id"])
            last = self._last_auto.get(asset_id)
            if last and (now - last).total_seconds() < 300:
                continue
            decision = automatic_execution_decision(export_kw, asset, bool(holds.get(asset_id)))
            if decision["action"] != "start":
                continue
            target = decision["target_power_kw"]
            power_result = await self.invoke_command(
                "energy.command.set_flexible_load_power",
                asset_id,
                {"requested_power_kw": target},
            )
            if power_result.get("status") != "CONFIRMED":
                break
            start_result = await self.invoke_command("energy.command.start_flexible_load", asset_id, {})
            if start_result.get("status") in {PENDING, "CONFIRMED"}:
                self._last_auto[asset_id] = now
            break

    async def async_stop(self) -> None:
        if callable(self._remove_runtime):
            self._remove_runtime()
        if callable(self._remove_timer):
            self._remove_timer()
        self._remove_runtime = None
        self._remove_timer = None
