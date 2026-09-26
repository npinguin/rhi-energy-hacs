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


class RuntimeCallbacks:
    """Keep global, topology and asset-scoped callback fanout outside the engine core."""

    def __init__(self) -> None:
        self.general: list[Callable[[], None]] = []
        self.topology: list[Callable[[], None]] = []
        self.assets: dict[str, list[Callable[[], None]]] = {}

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

    def notify_all(self) -> None:
        for cb in tuple(self.general):
            cb()
        for rows in tuple(self.assets.values()):
            for cb in tuple(rows):
                cb()

    def notify_assets(self, asset_ids: set[str]) -> None:
        for asset_id in asset_ids:
            for cb in tuple(self.assets.get(str(asset_id), ())):
                cb()

    def notify_topology(self) -> None:
        for cb in tuple(self.topology):
            cb()

    def clear(self) -> None:
        self.general.clear()
        self.topology.clear()
        self.assets.clear()
