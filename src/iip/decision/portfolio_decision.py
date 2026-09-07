"""Portfolio-level decision aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Decision, Verdict


@dataclass(frozen=True)
class PortfolioDecisionSummary:
    decisions: tuple[Decision, ...]

    @property
    def buy(self) -> tuple[Decision, ...]:
        return tuple(item for item in self.decisions if item.verdict == Verdict.COMPRAR)

    @property
    def reduce(self) -> tuple[Decision, ...]:
        return tuple(
            item
            for item in self.decisions
            if item.verdict in (Verdict.REDUZIR, Verdict.VENDER)
        )


def summarize(decisions: tuple[Decision, ...]) -> PortfolioDecisionSummary:
    return PortfolioDecisionSummary(decisions)
