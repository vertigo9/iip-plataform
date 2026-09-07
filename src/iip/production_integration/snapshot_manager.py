"""Production snapshot manager with monotonic revisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    portfolio_id: str
    revision: int
    as_of: str
    checksum: str
    payload: object


class SnapshotManager:
    def __init__(self) -> None:
        self._snapshots: dict[str, list[Snapshot]] = {}

    def save(
        self,
        portfolio_id: str,
        as_of: str,
        checksum: str,
        payload: object,
    ) -> Snapshot:
        versions = self._snapshots.setdefault(portfolio_id, [])
        revision = versions[-1].revision + 1 if versions else 1
        snapshot = Snapshot(portfolio_id, revision, as_of, checksum, payload)
        versions.append(snapshot)
        return snapshot

    def latest(self, portfolio_id: str) -> Snapshot | None:
        versions = self._snapshots.get(portfolio_id, [])
        return versions[-1] if versions else None
