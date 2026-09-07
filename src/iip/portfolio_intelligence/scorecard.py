"""Portfolio scorecard from explicit asset signals."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetScore:
    ticker: str
    score: float
    confidence: float
    action: str


@dataclass(frozen=True)
class PortfolioScorecard:
    items: tuple[AssetScore, ...]

    @property
    def average_score(self) -> float:
        if not self.items:
            return 0.0
        return round(sum(item.score for item in self.items) / len(self.items), 12)

    @property
    def high_conviction(self) -> tuple[AssetScore, ...]:
        return tuple(
            item for item in self.items if item.score >= 8 and item.confidence >= 0.70
        )
