"""Integrated IIP decision pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .allocation import rank
from .contribution import ContributionCandidate, prioritize_contributions
from .models import AssetSignal, PortfolioDecision


@dataclass(frozen=True)
class IntegratedPortfolioDecision:
    rankings: tuple[PortfolioDecision, ...]
    contribution_candidates: tuple[ContributionCandidate, ...]

    @property
    def top(self) -> PortfolioDecision | None:
        return self.rankings[0] if self.rankings else None


def run(signals: tuple[AssetSignal, ...]) -> IntegratedPortfolioDecision:
    rankings = rank(signals)
    return IntegratedPortfolioDecision(
        rankings=rankings,
        contribution_candidates=prioritize_contributions(rankings),
    )
