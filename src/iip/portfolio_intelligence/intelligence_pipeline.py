"""Portfolio intelligence pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .exposure import aggregate
from .holdings import Holding, normalize_holdings
from .manager_intelligence import aggregate_manager
from .scorecard import AssetScore, PortfolioScorecard
from .segment_intelligence import aggregate_segment


@dataclass(frozen=True)
class IntelligenceSnapshot:
    holdings: tuple[Holding, ...]
    scorecard: PortfolioScorecard
    manager_exposure: tuple
    segment_exposure: tuple
    asset_class_exposure: tuple


def build(
    holdings: tuple[Holding, ...],
    scores: tuple[AssetScore, ...],
) -> IntelligenceSnapshot:
    normalized = normalize_holdings(holdings)
    return IntelligenceSnapshot(
        holdings=normalized,
        scorecard=PortfolioScorecard(scores),
        manager_exposure=aggregate_manager(normalized),
        segment_exposure=aggregate_segment(normalized),
        asset_class_exposure=aggregate(normalized, "asset_class"),
    )
