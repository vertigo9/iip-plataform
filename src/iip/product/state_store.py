"""Persistent-style portfolio state store with versioning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateVersion:
    key: str
    version: int
    value: object


class PortfolioStateStore:
    def __init__(self) -> None:
        self._versions: dict[str, list[StateVersion]] = {}

    def save(self, key: str, value: object) -> StateVersion:
        versions = self._versions.setdefault(key, [])
        version = versions[-1].version + 1 if versions else 1
        item = StateVersion(key, version, value)
        versions.append(item)
        return item

    def latest(self, key: str) -> StateVersion | None:
        versions = self._versions.get(key, [])
        return versions[-1] if versions else None

    def history(self, key: str) -> tuple[StateVersion, ...]:
        return tuple(self._versions.get(key, ()))
