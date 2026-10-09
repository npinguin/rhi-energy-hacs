"""Vanilla EMHASS HTTP client. No EMHASS patches or private endpoints.

Read-only by default: never calls publish-data, never writes HA entities and
never issues physical commands. Caller owns validated canonical inputs.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


from .emhass_v0185_result import validate_native_run


class EmhassProtocolError(RuntimeError):
    pass


def validate_emhass_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("emhass_url_must_be_http_or_https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("emhass_url_must_be_service_origin")
    return value


@dataclass(frozen=True)
class EmhassRun:
    response: Any
    plan: Any | None
    last_run: Any | None


class VanillaEmhassClient:
    def __init__(self, hass, base_url: str, *, timeout_seconds: float = 30.0):
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        self._session = async_get_clientsession(hass)
        self.base_url = validate_emhass_url(base_url)
        self.timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()

    async def _request(self, method: str, path: str, payload=None):
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with self._session.request(
                method, f"{self.base_url}{path}", json=payload, timeout=timeout
            ) as response:
                if response.status >= 400:
                    raise EmhassProtocolError(f"http_{response.status}:{path}")
                text = await response.text()
                if not text:
                    return None
                try:
                    return await _parse_json(text)
                except ValueError:
                    return text
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise EmhassProtocolError(f"transport_failure:{type(exc).__name__}") from exc

    async def probe(self):
        """Probe optional vanilla config endpoint; never claim solver readiness."""
        return await self._request("GET", "/get-config")

    async def optimize_shadow(
        self,
        runtime_parameters: dict[str, Any],
        *,
        action: str = "naive-mpc-optim",
    ) -> EmhassRun:
        """Optimize without publishing data or issuing physical commands.

        Day-ahead ignores live soc_init; only MPC can use authoritative current
        battery SOC. The caller must supply complete and independently accepted
        canonical context. A valid HTTP response alone is never accepted.
        """
        if action not in {"naive-mpc-optim", "dayahead-optim"}:
            raise EmhassProtocolError("unsupported_optimization_action")
        if not runtime_parameters:
            raise ValueError("canonical_planning_inputs_required")
        if runtime_parameters.get("set_use_battery") is not False:
            if runtime_parameters.get("set_use_battery") is not True:
                raise EmhassProtocolError("battery_scope_must_be_explicit")
            if action == "dayahead-optim":
                raise EmhassProtocolError("dayahead_cannot_use_live_battery_soc")
            _validate_mpc_battery_soc(runtime_parameters)
        async with self._lock:
            before = await self._request("GET", "/api/v1/last-run")
            response = await self._request(
                "POST", f"/action/{action}", runtime_parameters
            )
            last_run = await self._request("GET", "/api/v1/last-run")
            if not isinstance(last_run, dict) or last_run.get("status") != "ok":
                raise EmhassProtocolError(
                    "optimizer_not_successful:" + str(
                        last_run.get("status") if isinstance(last_run, dict) else "invalid_response"
                    )
                )
            if last_run.get("action") != action:
                raise EmhassProtocolError("optimizer_action_mismatch")
            if last_run.get("infeasible") is True or last_run.get("error_message"):
                raise EmhassProtocolError("optimizer_infeasible_or_error")
            if (
                isinstance(before, dict)
                and before.get("timestamp")
                and before.get("timestamp") == last_run.get("timestamp")
            ):
                raise EmhassProtocolError("optimizer_run_not_advanced")
            plan = await self._request("GET", "/api/v1/plan")
            if (
                not isinstance(plan, dict)
                or plan.get("status") != "ok"
                or not isinstance(plan.get("plan"), list)
                or not plan["plan"]
            ):
                raise EmhassProtocolError("native_plan_not_available")
            validate_native_run(plan, last_run)
            return EmhassRun(response=response, plan=plan, last_run=last_run)


def _validate_mpc_battery_soc(payload: dict[str, Any]) -> None:
    from math import isfinite
    count = payload.get("number_of_batteries", 1)
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise EmhassProtocolError("invalid_battery_cardinality")
    def vector(key: str) -> list[float]:
        raw = payload.get(key)
        values = raw if isinstance(raw, list) else [raw]
        if len(values) != count or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x)
            for x in values
        ):
            raise EmhassProtocolError("invalid_battery_vector:" + key)
        return [float(x) for x in values]
    start, finish = vector("soc_init"), vector("soc_final")
    lower = vector("battery_minimum_state_of_charge")
    upper = vector("battery_maximum_state_of_charge")
    for index, (current, end, minimum, maximum) in enumerate(
        zip(start, finish, lower, upper, strict=True)
    ):
        if not (0 <= minimum <= current <= maximum <= 1):
            raise EmhassProtocolError(f"battery_soc_out_of_bounds:{index}")
        if not (minimum <= end <= maximum):
            raise EmhassProtocolError(f"battery_terminal_soc_out_of_bounds:{index}")


async def _parse_json(text: str):
    import json
    return json.loads(text)
