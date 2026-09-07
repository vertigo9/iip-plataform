"""Snapshot refresh planning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefreshTask:
    ticker: str
    source: str
    priority: int


def prioritize(tasks: tuple[RefreshTask, ...]) -> tuple[RefreshTask, ...]:
    return tuple(sorted(tasks, key=lambda t: (t.priority, t.ticker)))
