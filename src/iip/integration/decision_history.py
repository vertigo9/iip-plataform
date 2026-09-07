"""Decision history with explicit change detection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRecord:
    ticker: str
    score: float
    action: str
    evidence_ids: tuple[str, ...] = ()


def changed(previous: DecisionRecord | None, current: DecisionRecord) -> bool:
    if previous is None:
        return True
    return (
        previous.score != current.score
        or previous.action != current.action
        or previous.evidence_ids != current.evidence_ids
    )
