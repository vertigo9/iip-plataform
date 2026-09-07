"""Portfolio-level score aggregation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreComponent:
    ticker: str
    dimension: str
    score: float
    weight: float = 1.0


@dataclass(frozen=True)
class AssetScoreSummary:
    ticker: str
    score: float
    confidence: float
    dimensions: tuple[str, ...]


def aggregate(components: tuple[ScoreComponent, ...]) -> tuple[AssetScoreSummary, ...]:
    grouped = {}
    for item in components:
        key = item.ticker.upper()
        score, weight, dimensions = grouped.get(key, (0.0, 0.0, []))
        grouped[key] = (
            score + item.score * item.weight,
            weight + item.weight,
            [*dimensions, item.dimension],
        )
    return tuple(
        AssetScoreSummary(
            ticker,
            round(score / weight if weight else 0.0, 12),
            round(min(1.0, weight / 4.0), 12),
            tuple(dict.fromkeys(dimensions)),
        )
        for ticker, (score, weight, dimensions) in sorted(grouped.items())
    )
