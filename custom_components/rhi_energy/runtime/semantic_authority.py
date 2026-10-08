from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


class CanonicalFactStore(dict[str, Any]):
    """Dict-compatible canonical fact store with one effective writer per cycle.

    Existing runtime helpers intentionally keep their simple mapping API. The store
    adds ownership evidence underneath that API without introducing an event bus,
    expression engine or second semantic runtime.
    """

    def __init__(
        self,
        initial: dict[str, Any] | None = None,
        previous_paths: dict[str, Any] | None = None,
        previous_conflicts: list[dict[str, Any]] | None = None,
        *,
        track_writers: bool = True,
    ) -> None:
        # Runtime values are treated as immutable observations. A shallow mapping
        # copy is enough and avoids recursively copying the complete domain state.
        super().__init__(initial or {})
        self._track_writers = bool(track_writers)
        self._owner = "unscoped"
        self._allowed_previous: set[str] = set()
        self._cycle_writers: dict[str, str] = {}
        # Semantic ownership is structural truth. It is built during hydration /
        # model activation and reused unchanged during ordinary telemetry updates.
        self._paths: dict[str, dict[str, Any]] = (
            {} if track_writers else (previous_paths or {})
        )
        self._conflicts: list[dict[str, Any]] = list(previous_conflicts or [])
        self._changed_keys: set[str] = set()

    @contextmanager
    def writer(
        self,
        owner: str,
        *,
        resolves_from: set[str] | tuple[str, ...] = (),
    ) -> Iterator["CanonicalFactStore"]:
        if not self._track_writers:
            yield self
            return
        previous_owner = self._owner
        previous_allowed = self._allowed_previous
        self._owner = str(owner)
        self._allowed_previous = {str(value) for value in resolves_from}
        try:
            yield self
        finally:
            self._owner = previous_owner
            self._allowed_previous = previous_allowed

    def __setitem__(self, key: str, value: Any) -> None:
        fact_id = str(key)
        if not self._track_writers:
            previous_value = self.get(fact_id, object())
            super().__setitem__(fact_id, value)
            if previous_value != value:
                self._changed_keys.add(fact_id)
            return
        owner = self._owner
        previous = self._cycle_writers.get(fact_id)
        path = self._paths.setdefault(
            fact_id,
            {
                "semantic_owner": "rhi_energy",
                "candidate_writers": [],
                "selected_writer": None,
                "resolution_owner": None,
                "conflicts": [],
            },
        )
        if owner not in path["candidate_writers"]:
            path["candidate_writers"].append(owner)

        if previous is not None and previous != owner:
            if previous in self._allowed_previous:
                path["resolution_owner"] = owner
            else:
                issue = {
                    "fact_id": fact_id,
                    "reason": "MULTIPLE_EFFECTIVE_PRODUCERS",
                    "previous_writer": previous,
                    "candidate_writer": owner,
                }
                if issue not in path["conflicts"]:
                    path["conflicts"].append(issue)
                if issue not in self._conflicts:
                    self._conflicts.append(issue)
                # Fail closed: retain the already-selected canonical value.
                return

        previous_value = self.get(fact_id, object())
        super().__setitem__(fact_id, value)
        if previous_value != value:
            self._changed_keys.add(fact_id)
        self._cycle_writers[fact_id] = owner
        path["selected_writer"] = owner

    @property
    def conflicts(self) -> list[dict[str, Any]]:
        return list(self._conflicts)

    def semantic_paths(self) -> dict[str, dict[str, Any]]:
        return self._paths

    @property
    def changed_keys(self) -> frozenset[str]:
        return frozenset(self._changed_keys)

    @property
    def complete(self) -> bool:
        return not self._conflicts
