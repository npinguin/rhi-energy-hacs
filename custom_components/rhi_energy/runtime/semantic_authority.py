from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
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
    ) -> None:
        super().__init__(deepcopy(initial or {}))
        self._owner = "unscoped"
        self._allowed_previous: set[str] = set()
        self._cycle_writers: dict[str, str] = {}
        self._paths: dict[str, dict[str, Any]] = deepcopy(previous_paths or {})
        self._conflicts: list[dict[str, Any]] = []

    @contextmanager
    def writer(
        self,
        owner: str,
        *,
        resolves_from: set[str] | tuple[str, ...] = (),
    ) -> Iterator["CanonicalFactStore"]:
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

        super().__setitem__(fact_id, value)
        self._cycle_writers[fact_id] = owner
        path["selected_writer"] = owner

    @property
    def conflicts(self) -> list[dict[str, Any]]:
        return deepcopy(self._conflicts)

    def semantic_paths(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._paths)

    @property
    def complete(self) -> bool:
        return not self._conflicts
