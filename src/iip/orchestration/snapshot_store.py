"""In-memory snapshot index for deterministic testing and integration."""

from __future__ import annotations


class SnapshotStore:
    def __init__(self) -> None:
        self._snapshots: dict[str, object] = {}

    def put(self, key: str, value: object) -> None:
        self._snapshots[key] = value

    def get(self, key: str):
        return self._snapshots.get(key)

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._snapshots))
