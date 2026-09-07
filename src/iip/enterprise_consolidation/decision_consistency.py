"""Consistency across portfolio decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRecord:
    ticker: str
    action: str
    score: float


@dataclass(frozen=True)
class ConsistencyResult:
    consistent: bool
    conflicts: tuple[str, ...]


def check(records: tuple[DecisionRecord, ...]) -> ConsistencyResult:
    grouped: dict[str, set[str]] = {}
    for record in records:
        grouped.setdefault(record.ticker.upper(), set()).add(record.action.upper())

    conflicts = tuple(
        sorted(ticker for ticker, actions in grouped.items() if len(actions) > 1)
    )
    return ConsistencyResult(not conflicts, conflicts)
