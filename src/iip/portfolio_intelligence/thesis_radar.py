"""Thesis persistence radar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThesisPoint:
    ticker: str
    state: str
    evidence_count: int
    changed: bool


def prioritize(points: tuple[ThesisPoint, ...]) -> tuple[ThesisPoint, ...]:
    return tuple(
        sorted(
            points,
            key=lambda p: (
                not p.changed,
                -p.evidence_count,
                p.ticker.upper(),
            ),
        )
    )
