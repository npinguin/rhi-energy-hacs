"""Bound Home Assistant system-log noise without suppressing Energy runtime failures.

Telemetry failures are always retained by the source-materialization runtime
issues path. Only repeated log records are throttled per activated model.
"""
from __future__ import annotations

from typing import Any

WARNING_LIMIT = 25


class NormalizationLogGuard:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.failures: dict[tuple[str, str], str] = {}
        self.logged_keys: set[tuple[str, str]] = set()
        self.warning_count = 0
        self.saturated = False

    def failed(self, logger: Any, asset_id: Any, property_key: Any, exc: Exception) -> None:
        key = (str(asset_id or ""), str(property_key or ""))
        cause = type(exc).__name__
        if self.failures.get(key) == cause:
            return
        self.failures[key] = cause
        if self.warning_count < WARNING_LIMIT:
            logger.warning(
                "Energy property normalization failed asset=%s property=%s cause=%s",
                key[0], key[1], cause,
            )
            self.warning_count += 1
            self.logged_keys.add(key)
        elif not self.saturated:
            logger.warning(
                "Energy normalization warnings bounded at %s per model; "
                "additional failures remain in runtime_issues diagnostics",
                WARNING_LIMIT,
            )
            self.saturated = True

    def recovered(self, logger: Any, asset_id: Any, property_key: Any) -> None:
        key = (str(asset_id or ""), str(property_key or ""))
        previous = self.failures.pop(key, None)
        if previous is not None and key in self.logged_keys:
            self.logged_keys.discard(key)
            logger.info(
                "Energy property normalization recovered asset=%s property=%s prior_cause=%s",
                key[0], key[1], previous,
            )


def _guard(runtime: Any) -> NormalizationLogGuard:
    # Existing source-normalization regression harnesses borrow the real
    # _populate_direct_facts method without constructing EnergyRuntime.
    guard = getattr(runtime, "_normalization_log_guard", None)
    if guard is None:
        guard = NormalizationLogGuard()
        runtime._normalization_log_guard = guard
    return guard


def record_normalization_failure(
    runtime: Any, logger: Any, asset_id: Any, property_key: Any, exc: Exception,
) -> None:
    _guard(runtime).failed(logger, asset_id, property_key, exc)


def record_normalization_recovery(
    runtime: Any, logger: Any, asset_id: Any, property_key: Any,
) -> None:
    _guard(runtime).recovered(logger, asset_id, property_key)
