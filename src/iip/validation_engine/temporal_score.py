"""Temporal score aggregation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import HistoricalDecision


@dataclass(frozen=True)
class TemporalScore:
    ticker: str
    observations: int
    average_score: float
    latest_score: float


def aggregate(decisions: tuple[HistoricalDecision, ...]) -> tuple[TemporalScore, ...]:
    grouped = defaultdict(list)
    for decision in decisions:
        grouped[decision.ticker.upper()].append(decision)

    results = []
    for ticker, items in grouped.items():
        ordered = sorted(items, key=lambda item: item.date)
        results.append(
            TemporalScore(
                ticker=ticker,
                observations=len(ordered),
                average_score=round(
                    sum(item.score for item in ordered) / len(ordered), 2
                ),
                latest_score=ordered[-1].score,
            )
        )
    return tuple(sorted(results, key=lambda item: item.ticker))
