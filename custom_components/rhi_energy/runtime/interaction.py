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

from .canonical_semantics import (
    AVAILABLE,
    PENDING,
    UNSUPPORTED,
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
        providers = (((self.manager.domain_model or {}).get("concepts") or {}).get(concept) or {}).get("providers") or []
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

    def _logical_control(self, property_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
        if not property_id.startswith("logical:"):
            return None, None, None
        rest = property_id[len("logical:"):]
        asset_id, separator, property_key = rest.partition(":")
        if not separator or not asset_id or not property_key:
            return None, None, None
        asset = next(
            (
                row for row in self.runtime.snapshot.get("logical_assets") or []
                if str(row.get("asset_id") or "") == asset_id
            ),
            None,
        )
        prop = next(
            (
                row for row in (asset or {}).get("properties") or []
                if str(row.get("property_key") or "") == property_key
            ),
            None,
        )
        binding_ids = [str(item) for item in (prop or {}).get("binding_ids") or [] if item]
        if not binding_ids and (prop or {}).get("binding_id"):
            binding_ids = [str(prop["binding_id"])]
        if len(binding_ids) != 1:
            return asset, prop, None
        binding = next(
            (
                row for row in (self.manager.domain_model or {}).get("accepted_bindings") or []
                if str(row.get("binding_id") or "") == binding_ids[0]
            ),
            None,
        )
        return asset, prop, binding

    @staticmethod
    def _source_write_value(prop: dict[str, Any], binding: dict[str, Any], value: Any) -> Any:
        kind = str(prop.get("kind") or "")
        target_unit = str(((binding.get("technical_capability") or {}).get("native_unit")) or "")
        semantic_unit = str(prop.get("unit") or "")
        if kind == "power":
            numeric = number(value)
            if numeric is None:
                return None
            if semantic_unit == "kW" and target_unit == "W":
                return numeric * 1000.0
            if semantic_unit == "W" and target_unit == "kW":
                return numeric / 1000.0
            return numeric
        if kind in {"number", "voltage", "current", "temperature", "percentage", "duration", "count", "battery"}:
            return number(value)
        if kind == "boolean":
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"on", "true", "1", "enabled", "yes"}:
                return True
            if normalized in {"off", "false", "0", "disabled", "no"}:
                return False
            return None
        return str(value)

    async def _write_logical_property(self, property_id: str, value: Any) -> dict[str, Any]:
        result = {
            "property_id": property_id,
            "requested_value": value,
            "status": "REJECTED",
            "reason": "logical_property_unavailable",
        }
        asset, prop, binding = self._logical_control(property_id)
        if not asset or not prop or not binding:
            return result
        if prop.get("write_supported") is not True:
            result["reason"] = str(prop.get("control_reason") or "write_not_supported")
            return result
        source = binding.get("source_identity") or {}
        entity_id = str(source.get("current_entity_id") or "")
        platform = str(prop.get("platform") or "")
        if not entity_id or not entity_id.startswith(f"{platform}."):
            result["reason"] = "authoritative_write_surface_missing"
            return result

        state = self.hass.states.get(entity_id)
        attrs = dict(state.attributes) if state is not None else {}
        source_value = self._source_write_value(prop, binding, value)
        if source_value is None:
            result["reason"] = "invalid_value"
            return result

        if platform == "select":
            allowed = [str(item) for item in attrs.get("options") or []]
            source_value = str(source_value)
            if allowed and source_value not in allowed:
                result["reason"] = "outside_source_options"
                return result
            service, data = "select_option", {"entity_id": entity_id, "option": source_value}
        elif platform == "switch":
            service = "turn_on" if bool(source_value) else "turn_off"
            data = {"entity_id": entity_id}
        elif platform == "number":
            numeric = number(source_value)
            if numeric is None:
                result["reason"] = "invalid_number"
                return result
            minimum = number(attrs.get("min"))
            maximum = number(attrs.get("max"))
            if minimum is not None and numeric < minimum or maximum is not None and numeric > maximum:
                result["reason"] = "outside_source_constraints"
                return result
            service, data = "set_value", {"entity_id": entity_id, "value": numeric}
        else:
            result["reason"] = "unsafe_write_platform"
            return result

        await self.hass.services.async_call(platform, service, data, blocking=True)
        readback = self.hass.states.get(entity_id)
        if readback is None:
            result.update(status=PENDING, reason="write_dispatched_awaiting_readback")
            return result
        actual = self.runtime._convert(
            prop,
            readback.state,
            readback.attributes.get("unit_of_measurement")
            or (binding.get("technical_capability") or {}).get("native_unit"),
            dict(readback.attributes),
        )
        expected = value
        if isinstance(actual, (int, float)):
            expected = number(value)
            confirmed = expected is not None and abs(float(actual) - float(expected)) <= max(0.001, abs(float(expected)) * 0.001)
        elif isinstance(actual, bool):
            expected = self._source_write_value(prop, binding, value)
            confirmed = actual is expected
        else:
            confirmed = str(actual) == str(expected)
        result.update(
            status="CONFIRMED" if confirmed else PENDING,
            reason="authoritative_physical_readback_confirmed" if confirmed else "write_dispatched_readback_pending",
            readback_value=actual,
            target_asset_id=asset.get("asset_id"),
            source_platform=platform,
            source_entity_id=entity_id,
        )
        return result

    async def _admit_property_write(self, property_id: str, value: Any) -> dict[str, Any]:
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        fingerprint = hashlib.sha256(
            json.dumps(
                {"property_id": property_id, "value": value},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()[:20]
        row = {
            "operation_id": f"energy:property:{fingerprint}:{int(now.timestamp() * 1000)}",
            "fingerprint": fingerprint,
            "property_id": property_id,
            "requested_value": deepcopy(value),
            "requested_at": now.isoformat(),
            "deadline_at": (now + timedelta(seconds=COMMAND_TIMEOUT_SECONDS)).isoformat(),
            "status": PENDING,
            "reason": "admitted_pending_write",
            "readback_value": None,
        }
        self.store.data.setdefault("property_operation_state", {})[property_id] = row
        await self.store.async_save()
        return row

    def _finalize_property_write(self, operation: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        operation.update(
            status=result.get("status") or "REJECTED",
            reason=result.get("reason") or "unknown",
            readback_value=deepcopy(result.get("readback_value")),
            target_asset_id=result.get("target_asset_id"),
            source_platform=result.get("source_platform"),
            source_entity_id=result.get("source_entity_id"),
        )
        if operation["status"] in _TERMINAL:
            operation["completed_at"] = datetime.now(
                ZoneInfo(self.hass.config.time_zone)
            ).isoformat()
        result["operation_id"] = operation.get("operation_id")
        result["requested_at"] = operation.get("requested_at")
        result["completed_at"] = operation.get("completed_at")
        return result

    async def write_property(self, property_id: str, value: Any) -> dict[str, Any]:
        operation = await self._admit_property_write(property_id, value)
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
            "pricing.spot_price_current_eur_kwh": "spot_fallback_eur_kwh",
            "pricing.import_network_eur_kwh": "import_network_eur_kwh",
            "pricing.import_levies_eur_kwh": "import_levies_eur_kwh",
            "pricing.import_vat_pct": "import_vat_pct",
            "pricing.export_fee_eur_kwh": "export_fee_eur_kwh",
        }
        if property_id.startswith("logical:"):
            try:
                result = await self._write_logical_property(property_id, value)
            except Exception as exc:
                _LOGGER.exception("Energy property write failed property=%s", property_id)
                result.update(
                    status="REJECTED",
                    reason=f"property_write_exception:{type(exc).__name__}",
                )
        elif property_id in pricing_map:
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
            if normalized not in {"hour", "today", "week", "month", "year"}:
                result["reason"] = "invalid_period"
            else:
                settings["metering_selected_period"] = normalized
                result.update(status="CONFIRMED", reason="persisted_metering_context", readback_value=normalized)
        elif property_id.endswith(".ready_by"):
            asset_id = property_id[: -len(".ready_by")]
            asset = self._find_asset(asset_id)
            try:
                ready_by = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
                if ready_by.tzinfo is None:
                    ready_by = ready_by.replace(tzinfo=ZoneInfo(self.hass.config.time_zone))
            except (TypeError, ValueError):
                ready_by = None
            if asset is None or ready_by is None:
                result["reason"] = "asset_or_datetime_invalid"
            else:
                per_asset = settings.setdefault("flexible_loads", {}).setdefault(asset_id, {})
                per_asset["ready_by"] = ready_by.isoformat()
                result.update(
                    status="CONFIRMED",
                    reason="persisted_flexible_load_planning_intent",
                    readback_value=per_asset["ready_by"],
                )
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
            model = self.manager.domain_model or {}
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
                    source_entity_id=entity_id,
                    source_platform="number",
                )
        result = self._finalize_property_write(operation, result)
        self.store.data.setdefault("property_operation_state", {})[property_id] = operation
        self.store.add_activity(
            {
                "activity_type": "property_write",
                "property_id": property_id,
                "operation_id": result.get("operation_id"),
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
                    await self.store.async_save()
                    strategy = (self.store.data.get("settings") or {}).get("strategy", {})
                    mode = strategy.get("energy.automation_mode") or strategy.get("energy.operating_mode")
                    if mode == "automatic":
                        await self._execute_plan("resume")
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
        for property_id, operation in (self.store.data.get("property_operation_state") or {}).items():
            if operation.get("status") != PENDING:
                continue
            deadline = operation.get("deadline_at")
            try:
                expired = bool(deadline and now >= datetime.fromisoformat(str(deadline)))
            except (TypeError, ValueError):
                expired = False
            requested = operation.get("requested_value")
            actual = None
            if str(property_id).startswith("logical:"):
                asset, prop, _binding = self._logical_control(str(property_id))
                if asset and prop:
                    current = next(
                        (
                            row for row in (self.runtime.snapshot.get("logical_assets") or [])
                            if str(row.get("asset_id") or "") == str(asset.get("asset_id") or "")
                        ),
                        None,
                    )
                    current_prop = next(
                        (
                            row for row in (current or {}).get("properties") or []
                            if str(row.get("property_key") or "") == str(prop.get("property_key") or "")
                        ),
                        None,
                    )
                    actual = (current_prop or {}).get("value")
            source_entity_id = operation.get("source_entity_id")
            if actual is None and str(property_id).endswith(".requested_power_kw"):
                asset_id = str(property_id)[: -len(".requested_power_kw")]
                asset = self._find_asset(asset_id)
                actual = (asset or {}).get("requested_power_kw")
            if actual is None and source_entity_id:
                state = self.hass.states.get(str(source_entity_id))
                actual = number(state.state) if state is not None else None
            expected_number = number(requested)
            actual_number = number(actual)
            confirmed = (
                actual_number is not None
                and expected_number is not None
                and abs(actual_number - expected_number)
                    <= max(0.001, abs(expected_number) * 0.001)
            ) or (
                actual is not None
                and expected_number is None
                and str(actual) == str(requested)
            )
            if confirmed:
                operation.update(
                    status="CONFIRMED",
                    reason="authoritative_property_readback_confirmed",
                    readback_value=actual,
                    completed_at=now.isoformat(),
                )
                changed = True
            elif expired:
                operation.update(
                    status="TIMED_OUT",
                    reason="authoritative_property_readback_timeout",
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
                availability = AVAILABLE if ready else (
                    UNSUPPORTED
                    if producer is None and role not in {"pause", "resume"}
                    else "UNAVAILABLE"
                )
                blocked_reason = None if ready else "producer_command_unavailable"
                label = {
                    "start": "Start charging",
                    "stop": "Stop charging",
                    "adjust": "Requested charge power",
                    "pause": "Pause managed charging",
                    "resume": "Resume managed charging",
                }[role]
                rows.append(
                    {
                        "command_instance_id": f"{command_id}.{asset_id}",
                        "command_id": command_id,
                        "owner": "energy",
                        "command_owner": "energy",
                        "target_asset_id": asset_id,
                        "role": role,
                        "label": label,
                        "action_kind": "command",
                        "supported": supported,
                        "availability": availability,
                        "state": "available" if ready else "unavailable",
                        # The UX consumes owner-published visibility/readiness. It must
                        # never infer these semantics from availability or role names.
                        "visible": supported,
                        "ux_visible": supported,
                        "enabled": ready,
                        "ux_enabled": ready,
                        "blocked_reason": blocked_reason,
                        "user_action_text": "" if ready else "Physical command is not currently published/ready by the producer domain.",
                        "reason": {
                            "code": blocked_reason,
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
                            "service": "rhi_energy.invoke_command",
                            "data": {"command_id": command_id, "target_asset_id": asset_id, "parameters": {}},
                        },
                        "readback": {
                            "command_instance_id": f"{command_id}.{asset_id}",
                            "state": str(last.get("status") or "IDLE").lower(),
                            "result_code": last.get("reason"),
                            "feedback_confirmed": last.get("status") == "CONFIRMED",
                        },
                        "operation_id": last.get("operation_id"),
                        "status": last.get("status") or "IDLE",
                        "requested_at": last.get("requested_at"),
                        "completed_at": last.get("completed_at"),
                        "execution_evidence": {
                            "dispatch_state": last.get("dispatch_state"),
                            "producer_domain": last.get("producer_domain"),
                            "result_code": last.get("reason"),
                            "feedback_confirmed": last.get("status") == "CONFIRMED",
                        },
                        "execution_status": last.get("status") or "IDLE",
                        "authoritative_readback_ref": "energy:contract:flexible_plan",
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
                        "service": "rhi_energy.invoke_command",
                        "data": {"command_id": command_id, "target_asset_id": "metering", "period_id": period, "parameters": {}},
                    },
                    "readback": {
                        "command_instance_id": f"{command_id}.{period}.metering",
                        "state": str(last.get("status") or "IDLE").lower(),
                        "result_code": last.get("reason"),
                        "feedback_confirmed": last.get("status") == "CONFIRMED",
                    },
                    "operation_id": last.get("operation_id"),
                    "status": last.get("status") or "IDLE",
                    "requested_at": last.get("requested_at"),
                    "completed_at": last.get("completed_at"),
                    "execution_evidence": {
                        "dispatch_state": last.get("dispatch_state"),
                        "producer_domain": last.get("producer_domain") or "energy",
                        "result_code": last.get("reason"),
                        "feedback_confirmed": last.get("status") == "CONFIRMED",
                    },
                    "execution_status": last.get("status") or "IDLE",
                    "authoritative_readback_ref": "energy:object:metering",
                }
            )
        execute_command_id = "energy.command.execute_plan"
        execute_key = command_state_key(execute_command_id, "energy")
        execute_last = states.get(execute_key, {})
        rows.append(
            {
                "command_instance_id": "energy.command.execute_plan.energy",
                "command_id": execute_command_id,
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
                    "service": "rhi_energy.invoke_command",
                    "data": {"command_id": "energy.command.execute_plan", "target_asset_id": "energy", "parameters": {}},
                },
                "readback": {
                    "state": str(execute_last.get("status") or "IDLE").lower(),
                    "result_code": execute_last.get("reason"),
                    "feedback_confirmed": execute_last.get("status") == "CONFIRMED",
                },
                "operation_id": execute_last.get("operation_id"),
                "status": execute_last.get("status") or "IDLE",
                "requested_at": execute_last.get("requested_at"),
                "completed_at": execute_last.get("completed_at"),
                "execution_evidence": {
                    "dispatch_state": execute_last.get("dispatch_state"),
                    "producer_domain": "energy",
                    "result_code": execute_last.get("reason"),
                    "feedback_confirmed": execute_last.get("status") == "CONFIRMED",
                },
                "execution_status": execute_last.get("status") or "IDLE",
                "authoritative_readback_ref": "energy:contract:planning",
            }
        )
        return rows

    async def _automatic_tick(self, _now) -> None:
        strategy = (self.store.data.get("settings") or {}).get("strategy", {})
        mode = strategy.get("energy.automation_mode") or strategy.get("energy.operating_mode")
        if mode != "automatic":
            return
        await self._execute_plan("automatic")

    @staticmethod
    def _current_plan_allocations(snapshot: dict[str, Any], now: datetime) -> tuple[dict[str, dict[str, Any]], str]:
        plan = snapshot.get("plan") or {}
        d0 = (plan.get("planning_horizons") or {}).get("D0") or {}
        if ((d0.get("quality") or {}).get("availability")) != AVAILABLE:
            return {}, "planning_horizon_unavailable"
        for bucket in d0.get("buckets") or []:
            try:
                start = datetime.fromisoformat(str(bucket.get("start_time") or bucket.get("start_at")))
                end = datetime.fromisoformat(str(bucket.get("end_time") or bucket.get("end_at")))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=now.tzinfo)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=now.tzinfo)
            except (TypeError, ValueError):
                continue
            if start <= now < end:
                rows = {
                    str(row.get("asset_id")): deepcopy(row)
                    for row in bucket.get("asset_allocations") or []
                    if isinstance(row, dict) and row.get("asset_id")
                }
                return rows, "current_d0_bucket"
        return {}, "no_current_planning_bucket"

    async def _execute_plan(self, origin: str) -> None:
        snap = self.runtime.snapshot
        facts = snap.get("facts") or {}
        holds = (self.store.data.get("settings") or {}).get("holds", {})
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        assets = list(snap.get("flexible_assets", []))
        allocations, plan_reason = self._current_plan_allocations(snap, now)

        # Protective control always wins over positive scheduling.
        protected: set[str] = set()
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
                    protected.add(asset_id)
                    self._last_auto[asset_id] = now

        if not allocations and plan_reason != "current_d0_bucket":
            self.store.add_activity({
                "activity_type": "plan_execution",
                "origin": origin,
                "status": "not_executed",
                "reason": plan_reason,
            })
            await self.store.async_save()
            self._notify()
            return

        for asset in assets:
            asset_id = str(asset["asset_id"])
            if asset_id in protected:
                continue
            allocation = allocations.get(asset_id)
            held = bool(holds.get(asset_id))
            operating = str(asset.get("operating_state") or "").lower()
            running = operating in {"running", "charging", "active", "on"}

            # A managed hold or absence from the current plan bucket means this
            # load must not consume flexible energy in this bucket.
            if held or allocation is None:
                if running:
                    result = await self.invoke_command(
                        "energy.command.stop_flexible_load", asset_id, {}
                    )
                    if result.get("status") in {PENDING, "CONFIRMED"}:
                        self._last_auto[asset_id] = now
                continue

            target = number(allocation.get("planned_power_kw"))
            if target is None or target <= 0:
                if running:
                    await self.invoke_command(
                        "energy.command.stop_flexible_load", asset_id, {}
                    )
                continue

            current_request = number(asset.get("requested_power_kw"))
            if current_request is None or abs(current_request - target) > 0.11:
                power_result = await self.invoke_command(
                    "energy.command.set_flexible_load_power",
                    asset_id,
                    {"requested_power_kw": target},
                )
                # Physical setpoint readback is authoritative. The next timer/event
                # cycle continues only after the durable command becomes CONFIRMED.
                if power_result.get("status") != "CONFIRMED":
                    continue

            if not running:
                start_result = await self.invoke_command(
                    "energy.command.start_flexible_load", asset_id, {}
                )
                if start_result.get("status") in {PENDING, "CONFIRMED"}:
                    self._last_auto[asset_id] = now

        self.store.add_activity({
            "activity_type": "plan_execution",
            "origin": origin,
            "status": "evaluated",
            "reason": plan_reason,
            "planned_asset_count": len(allocations),
        })
        await self.store.async_save()
        self._notify()

    async def async_stop(self) -> None:
        if callable(self._remove_runtime):
            self._remove_runtime()
        if callable(self._remove_timer):
            self._remove_timer()
        self._remove_runtime = None
        self._remove_timer = None
