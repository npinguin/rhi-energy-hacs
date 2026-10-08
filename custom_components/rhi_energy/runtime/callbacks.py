"""Bounded runtime callback routing for Energy."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def logical_topology(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(sorted(
        (
            str(asset.get("asset_id") or ""),
            str(asset.get("object_class") or ""),
            tuple(sorted(
                str(prop.get("property_key") or "")
                for prop in (asset.get("properties") or [])
                if isinstance(prop, dict) and prop.get("property_key")
            )),
        )
        for asset in (snapshot.get("logical_assets") or [])
        if isinstance(asset, dict) and asset.get("asset_id")
    ))


def changed_logical_asset_ids(
    previous_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    current_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    full_hydration: bool,
) -> set[str]:
    previous = {
        str(row.get("asset_id") or ""): row
        for row in previous_rows
        if isinstance(row, dict) and row.get("asset_id")
    }
    current = {
        str(row.get("asset_id") or ""): row
        for row in current_rows
        if isinstance(row, dict) and row.get("asset_id")
    }
    if full_hydration:
        return set(current)
    return {
        asset_id
        for asset_id in set(previous) | set(current)
        if previous.get(asset_id) != current.get(asset_id)
    }


class RuntimeCallbacks:
    """Keep global, topology and asset-scoped callback fanout outside the engine core."""

    def __init__(self) -> None:
        self.general: list[Callable[[], None]] = []
        self.topology: list[Callable[[], None]] = []
        self.public: list[Callable[[], None]] = []
        self.assets: dict[str, list[Callable[[], None]]] = {}
        self.general_notify_count = 0
        self.asset_notify_batch_count = 0
        self.asset_callback_count = 0
        self.full_asset_fanout_count = 0
        self.public_notify_count = 0

    @staticmethod
    def _remove(rows: list[Callable[[], None]], cb: Callable[[], None]) -> None:
        if cb in rows:
            rows.remove(cb)

    def add(self, cb: Callable[[], None]):
        self.general.append(cb)
        return lambda: self._remove(self.general, cb)

    def add_topology(self, cb: Callable[[], None]):
        self.topology.append(cb)
        return lambda: self._remove(self.topology, cb)

    def add_public(self, cb: Callable[[], None]):
        self.public.append(cb)
        return lambda: self._remove(self.public, cb)

    def add_asset(self, asset_id: str, cb: Callable[[], None]):
        key = str(asset_id)
        rows = self.assets.setdefault(key, [])
        rows.append(cb)

        def remove() -> None:
            current = self.assets.get(key)
            if current:
                self._remove(current, cb)
                if not current:
                    self.assets.pop(key, None)

        return remove

    def notify_general(self) -> None:
        self.general_notify_count += 1
        for cb in tuple(self.general):
            cb()

    def notify_all(self) -> None:
        self.full_asset_fanout_count += 1
        self.notify_general()
        self.notify_public()
        self.notify_assets(set(self.assets))

    def notify_public(self) -> None:
        self.public_notify_count += 1
        for cb in tuple(self.public):
            cb()

    def notify_assets(self, asset_ids: set[str]) -> None:
        if not asset_ids:
            return
        self.asset_notify_batch_count += 1
        for asset_id in asset_ids:
            for cb in tuple(self.assets.get(str(asset_id), ())):
                self.asset_callback_count += 1
                cb()

    def diagnostics(self) -> dict[str, int]:
        return {
            "general_listener_count": len(self.general),
            "topology_listener_count": len(self.topology),
            "public_listener_count": len(self.public),
            "asset_listener_asset_count": len(self.assets),
            "asset_listener_count": sum(len(rows) for rows in self.assets.values()),
            "general_notify_count": self.general_notify_count,
            "asset_notify_batch_count": self.asset_notify_batch_count,
            "asset_callback_count": self.asset_callback_count,
            "full_asset_fanout_count": self.full_asset_fanout_count,
            "public_notify_count": self.public_notify_count,
        }

    def notify_topology(self) -> None:
        for cb in tuple(self.topology):
            cb()

    def clear(self) -> None:
        self.general.clear()
        self.topology.clear()
        self.public.clear()
        self.assets.clear()
