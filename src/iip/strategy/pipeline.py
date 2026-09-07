"""Integrated portfolio strategy pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .allocation_planner import plan as plan_allocation
from .income_plan import build as build_income
from .models import StrategyInput
from .report import StrategyReport
from .strategy_engine import decide


@dataclass(frozen=True)
class StrategyPipelineInput:
    as_of: str
    assets: tuple[StrategyInput, ...]
    current_income: float
    target_income: float
    current_weights: tuple[tuple[str, float], ...]
    target_weights: tuple[tuple[str, float], ...]


def run(data: StrategyPipelineInput) -> StrategyReport:
    decisions = tuple(
        sorted(
            (decide(asset) for asset in data.assets),
            key=lambda x: (-x.priority_score, x.ticker),
        )
    )
    income_plan = build_income(data.current_income, data.target_income)
    allocation = plan_allocation(data.current_weights, data.target_weights)
    return StrategyReport(data.as_of, decisions, income_plan, allocation)
