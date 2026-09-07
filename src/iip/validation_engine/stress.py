"""Stress testing for decision rules."""

from __future__ import annotations

from dataclasses import dataclass

from .models import HistoricalDecision


@dataclass(frozen=True)
class StressScenario:
    name: str
    return_shock: float
    income_shock: float


@dataclass(frozen=True)
class StressResult:
    scenario: str
    observations: int
    average_return: float
    average_income: float
    worst_return: float


def apply_scenario(
    decisions: tuple[HistoricalDecision, ...],
    scenario: StressScenario,
) -> StressResult:
    returns = []
    incomes = []
    for decision in decisions:
        if decision.realized_return is None:
            continue
        returns.append(decision.realized_return + scenario.return_shock)
        incomes.append((decision.realized_income or 0.0) + scenario.income_shock)

    return StressResult(
        scenario=scenario.name,
        observations=len(returns),
        average_return=sum(returns) / len(returns) if returns else 0.0,
        average_income=sum(incomes) / len(incomes) if incomes else 0.0,
        worst_return=min(returns) if returns else 0.0,
    )


DEFAULT_STRESS_SCENARIOS = (
    StressScenario("market_-10pct", -0.10, 0.00),
    StressScenario("market_-20pct", -0.20, -0.05),
    StressScenario("market_-30pct", -0.30, -0.10),
)
