"""Contribution priority engine for the IIP monthly contribution workflow."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Action, PortfolioDecision


@dataclass(frozen=True)
class ContributionCandidate:
    ticker: str
    score: float
    monthly_budget_share: float


def prioritize_contributions(
    decisions: tuple[PortfolioDecision, ...],
) -> tuple[ContributionCandidate, ...]:
    buy = [item for item in decisions if item.action == Action.APORTAR]
    total = sum(max(0.0, item.allocation_score) for item in buy)
    if total <= 0:
        return ()
    return tuple(
        ContributionCandidate(
            ticker=item.ticker,
            score=item.allocation_score,
            monthly_budget_share=round(item.allocation_score / total, 4),
        )
        for item in sorted(buy, key=lambda item: (-item.allocation_score, item.ticker))
    )
