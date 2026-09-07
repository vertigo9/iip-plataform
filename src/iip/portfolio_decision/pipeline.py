"""Consolidated portfolio decision pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .executive_report import ExecutiveReport
from .income_intelligence import IncomeObservation, summarize
from .opportunity import Opportunity, rank
from .risk_synthesis import RiskObservation, synthesize
from .score_aggregation import ScoreComponent, aggregate


@dataclass(frozen=True)
class PortfolioDecisionInput:
    as_of: str
    scores: tuple[ScoreComponent, ...]
    income: tuple[IncomeObservation, ...]
    risks: tuple[RiskObservation, ...]
    opportunities: tuple[Opportunity, ...]


def run(data: PortfolioDecisionInput) -> ExecutiveReport:
    score_summary = aggregate(data.scores)
    income_summary = summarize(data.income)
    risk_summary = synthesize(data.risks)
    opportunities = rank(data.opportunities)
    return ExecutiveReport(
        data.as_of,
        score_summary,
        income_summary,
        risk_summary,
        opportunities,
    )
