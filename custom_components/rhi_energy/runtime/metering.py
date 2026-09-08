"""Persistent event-driven Energy metering with evidence-sticky quality semantics.

Metering integrates event-driven power but learns baseload on a fixed wall-clock cadence,
so noisy integrations cannot get more statistical weight merely because they publish more
often. Store writes for measurement/learning state are bounded by a debounce interval;
command admission uses the store directly and is therefore not delayed by this module.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

BASELOAD_SAMPLE_MINUTES = 15
PERSIST_DEBOUNCE_SECONDS = 10


def _period_keys(now: datetime) -> dict[str, str]:
    iso = now.isocalendar()
    return {
        "today": now.strftime("%Y-%m-%d"),
        "week": f"{iso.year}-W{iso.week:02d}",
        "month": now.strftime("%Y-%m"),
        "year": now.strftime("%Y"),
    }


def _period_start(now: datetime, period_id: str) -> datetime:
    if period_id == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period_id == "week":
        start = now - timedelta(days=now.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    if period_id == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _sticky_field_quality(previous: str | None, *, observed: bool, gap: bool = False) -> str:
    """Advance field quality without ever healing a proven evidence gap."""
    prev = str(previous or "UNKNOWN")
    if gap and (observed or prev in {"OK", "PARTIAL"}):
        return "PARTIAL"
    if prev == "PARTIAL":
        return "PARTIAL"
    if observed:
        return "OK"
    return prev if prev in {"OK", "PARTIAL"} else "UNKNOWN"


def _overall_quality(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    qualities = row.get("field_quality") or {}
    values = [str(qualities.get(field) or "UNKNOWN") for field in fields]
    if any(value == "PARTIAL" for value in values):
        return "PARTIAL"
    if values and all(value == "OK" for value in values):
        return "OK"
    if any(value == "OK" for value in values):
        return "PARTIAL"
    return "UNKNOWN"


def _new_period(period_key: str) -> dict[str, Any]:
    fields = EnergyMetering.FIELDS
    return {
        "period_key": period_key,
        "quality": "UNKNOWN",
        "flexible_assets_kwh": {},
        "field_quality": {field: "UNKNOWN" for field in fields},
        "field_coverage_seconds": {field: 0 for field in fields},
        "baseline_reset_at": None,
        "gap_count": 0,
        **{field: None for field in fields},
    }


def _baseload_bucket(now: datetime) -> str:
    minute = (now.minute // BASELOAD_SAMPLE_MINUTES) * BASELOAD_SAMPLE_MINUTES
    return now.replace(minute=minute, second=0, microsecond=0).isoformat()


class EnergyMetering:
    FIELDS = (
        "solar_kwh",
        "grid_import_kwh",
        "grid_export_kwh",
        "consumption_kwh",
        "battery_charge_kwh",
        "battery_discharge_kwh",
        "flexible_load_kwh",
    )

    def __init__(self, hass: HomeAssistant, store, runtime) -> None:
        self.hass = hass
        self.store = store
        self.runtime = runtime
        self._remove = None
        self._callbacks: list[Callable[[], None]] = []
        self._save_task: asyncio.Task | None = None

    def add_callback(self, cb):
        self._callbacks.append(cb)
        return lambda: self._callbacks.remove(cb) if cb in self._callbacks else None

    def _notify(self) -> None:
        for cb in tuple(self._callbacks):
            cb()

    async def async_start(self) -> None:
        self._remove = self.runtime.add_callback(self.update)
        self.update()

    def _ensure_periods(self, now: datetime) -> dict[str, Any]:
        state = self.store.data.setdefault("metering", {})
        state.setdefault("periods", {})
        state.setdefault("last_update", None)
        state.setdefault("last_powers", {})
        state.setdefault("last_flexible_powers", {})
        state.setdefault("baseload_profile", {})
        state.setdefault("baseload_last_sample_bucket", None)
        keys = _period_keys(now)
        for period_id, key in keys.items():
            row = state["periods"].get(period_id)
            if not isinstance(row, dict) or row.get("period_key") != key:
                state["periods"][period_id] = _new_period(key)
            else:
                row.setdefault("quality", "UNKNOWN")
                row.setdefault("flexible_assets_kwh", {})
                row.setdefault("field_quality", {field: "UNKNOWN" for field in self.FIELDS})
                row.setdefault("field_coverage_seconds", {field: 0 for field in self.FIELDS})
                row.setdefault("baseline_reset_at", None)
                row.setdefault("gap_count", 0)
                for field in self.FIELDS:
                    row.setdefault(field, None)
                    row["field_quality"].setdefault(field, "UNKNOWN")
                    row["field_coverage_seconds"].setdefault(field, 0)
        return state

    @staticmethod
    def _accumulate(row: dict[str, Any], field: str, kw: float, hours: float, seconds: float) -> None:
        current = row.get(field)
        row[field] = round((float(current) if current is not None else 0.0) + max(0.0, float(kw)) * hours, 6)
        quality = row.setdefault("field_quality", {})
        quality[field] = _sticky_field_quality(quality.get(field), observed=True)
        coverage = row.setdefault("field_coverage_seconds", {})
        coverage[field] = int(coverage.get(field, 0)) + int(max(0, seconds))

    @staticmethod
    def _mark_gap(row: dict[str, Any], last: dict[str, Any], now: datetime) -> None:
        qualities = row.setdefault("field_quality", {})
        had_evidence = False
        for field in EnergyMetering.FIELDS:
            observed = isinstance(last.get(field), (int, float)) or row.get(field) is not None
            qualities[field] = _sticky_field_quality(qualities.get(field), observed=observed, gap=True)
            had_evidence = had_evidence or observed
        if had_evidence:
            row["gap_count"] = int(row.get("gap_count") or 0) + 1
            row["gap_detected_at"] = now.isoformat()
        row["quality"] = _overall_quality(row, EnergyMetering.FIELDS)

    @staticmethod
    def _effective_start(row: dict[str, Any], natural_start: datetime, prev: datetime) -> datetime:
        start = max(prev, natural_start)
        reset_at = row.get("baseline_reset_at")
        if reset_at:
            try:
                reset = datetime.fromisoformat(str(reset_at))
                if reset.tzinfo is None and prev.tzinfo is not None:
                    reset = reset.replace(tzinfo=prev.tzinfo)
                start = max(start, reset)
            except (TypeError, ValueError):
                pass
        return start

    def _learn_baseload(self, now: datetime, facts: dict[str, Any], flexible_kw: float | None) -> None:
        home = facts.get("home_consumption.power_kw")
        if not isinstance(home, (int, float)) or flexible_kw is None:
            return
        state = self.store.data.setdefault("metering", {})
        bucket = _baseload_bucket(now)
        if state.get("baseload_last_sample_bucket") == bucket:
            return
        state["baseload_last_sample_bucket"] = bucket
        base = max(0.0, float(home) - max(0.0, float(flexible_kw)))
        profile = state.setdefault("baseload_profile", {})
        key = f"{now.hour:02d}"
        row = profile.get(key) if isinstance(profile.get(key), dict) else {"avg_kw": 0.0, "samples": 0}
        samples = min(200, int(row.get("samples", 0)))
        avg = float(row.get("avg_kw", 0.0))
        next_samples = samples + 1
        next_avg = base if samples == 0 else avg + (base - avg) / next_samples
        profile[key] = {
            "avg_kw": round(next_avg, 4),
            "samples": next_samples,
            "last_sample_at": now.isoformat(),
            "sample_bucket": bucket,
        }

    def _schedule_save(self) -> None:
        if self._save_task is not None and not self._save_task.done():
            return

        async def _save_later() -> None:
            try:
                await asyncio.sleep(PERSIST_DEBOUNCE_SECONDS)
                await self.store.async_save()
            finally:
                self._save_task = None

        self._save_task = self.hass.async_create_task(_save_later())

    def update(self) -> None:
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        state = self._ensure_periods(now)
        snap = self.runtime.snapshot
        facts = snap.get("facts") or {}
        flexible_rows = [a for a in snap.get("flexible_assets", []) if a.get("asset_id")]
        flexible_powers = {
            str(a["asset_id"]): a.get("power_kw")
            for a in flexible_rows
            if isinstance(a.get("power_kw"), (int, float))
        }
        flexible_total = (
            sum(float(value) for value in flexible_powers.values())
            if flexible_rows and len(flexible_powers) == len(flexible_rows)
            else (0.0 if not flexible_rows else None)
        )
        current = {
            "solar_kwh": facts.get("solar.power_kw"),
            "grid_import_kwh": facts.get("grid_import.power_kw"),
            "grid_export_kwh": facts.get("grid_export.power_kw"),
            "consumption_kwh": facts.get("home_consumption.power_kw"),
            "battery_charge_kwh": max(0.0, -facts.get("battery.power_kw")) if isinstance(facts.get("battery.power_kw"), (int, float)) else None,
            "battery_discharge_kwh": max(0.0, facts.get("battery.power_kw")) if isinstance(facts.get("battery.power_kw"), (int, float)) else None,
            "flexible_load_kwh": flexible_total,
        }
        last_at = state.get("last_update")
        last = state.get("last_powers") or {}
        last_flexible = state.get("last_flexible_powers") or {}
        try:
            prev = datetime.fromisoformat(last_at) if last_at else None
        except (TypeError, ValueError):
            prev = None
        dt = (now - prev).total_seconds() if prev else 0

        if prev is not None and 0 < dt <= 300:
            for period_id, row in state["periods"].items():
                start = self._effective_start(row, _period_start(now, period_id), prev)
                seconds = max(0.0, (now - start).total_seconds())
                if seconds <= 0:
                    continue
                hours = seconds / 3600.0
                for field in self.FIELDS:
                    kw = last.get(field)
                    if isinstance(kw, (int, float)):
                        self._accumulate(row, field, float(kw), hours, seconds)
                for asset_id, kw in last_flexible.items():
                    if isinstance(kw, (int, float)):
                        per = row.setdefault("flexible_assets_kwh", {})
                        per[asset_id] = round(float(per.get(asset_id) or 0.0) + max(0.0, float(kw)) * hours, 6)
                row["quality"] = _overall_quality(row, self.FIELDS)
        elif prev is not None and dt > 300:
            for row in state["periods"].values():
                self._mark_gap(row, last, now)

        self._learn_baseload(now, facts, flexible_total)
        state["last_update"] = now.isoformat()
        state["last_powers"] = current
        state["last_flexible_powers"] = flexible_powers
        self._notify()
        self._schedule_save()

    async def reset_period(self, period_id: str) -> bool:
        if period_id not in {"today", "week", "month", "year"}:
            return False
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        state = self._ensure_periods(now)
        row = state["periods"][period_id]
        for field in self.FIELDS:
            row[field] = None
        row["flexible_assets_kwh"] = {}
        row["field_quality"] = {field: "UNKNOWN" for field in self.FIELDS}
        row["field_coverage_seconds"] = {field: 0 for field in self.FIELDS}
        row["quality"] = "UNKNOWN"
        row["baseline_reset_at"] = now.isoformat()
        row["gap_count"] = 0
        row.pop("gap_detected_at", None)
        self.store.add_activity({"activity_type": "metering_reset", "period_id": period_id, "status": "confirmed"})
        await self.store.async_save()
        self._notify()
        return True

    async def async_stop(self) -> None:
        if callable(self._remove):
            self._remove()
        self._remove = None
        if self._save_task is not None and not self._save_task.done():
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
            self._save_task = None
            await self.store.async_save()
