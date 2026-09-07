"""Persistence hardening contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersistedState:
    key: str
    revision: int
    checksum: str
    payload: object


def next_revision(
    previous: PersistedState | None, checksum: str, payload: object
) -> PersistedState:
    revision = previous.revision + 1 if previous else 1
    return PersistedState(
        key=previous.key if previous else "state",
        revision=revision,
        checksum=checksum,
        payload=payload,
    )
