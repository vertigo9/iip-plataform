"""Executive portfolio report."""

from __future__ import annotations

from dataclasses import dataclass

from .income_intelligence import IncomeSummary
from .opportunity import Opportunity
from .risk_synthesis import RiskSynthesis
from .score_aggregation import AssetScoreSummary


@dataclass(frozen=True)
class ExecutiveReport:
    as_of: str
    score_summaries: tuple[AssetScoreSummary, ...]
    income_summaries: tuple[IncomeSummary, ...]
    risk_summaries: tuple[RiskSynthesis, ...]
    opportunities: tuple[Opportunity, ...]

    @property
    def top_opportunity(self) -> Opportunity | None:
        return self.opportunities[0] if self.opportunities else None
