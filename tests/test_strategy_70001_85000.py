from iip.strategy.allocation_planner import plan
from iip.strategy.dividend_priority import DividendCandidate
from iip.strategy.dividend_priority import rank as rank_div
from iip.strategy.e2e import execute
from iip.strategy.history import DecisionPoint, action_changed
from iip.strategy.income_plan import build as build_income
from iip.strategy.margin_matrix import MarginPoint
from iip.strategy.margin_matrix import rank as rank_margin
from iip.strategy.models import StrategyInput
from iip.strategy.pipeline import StrategyPipelineInput, run
from iip.strategy.risk_budget import assess
from iip.strategy.strategy_engine import build_signal, decide


def sample():
    return StrategyInput("HGRU11", 9, 0.9, 0.08, 0.20, 3, 0.05, 0.10)


def test_strategy_signal():
    signal = build_signal(sample())
    assert signal.ticker == "HGRU11"
    assert signal.quality_score == 8.1
    assert signal.allocation_gap == 0.05


def test_strategy_decision():
    decision = decide(sample())
    assert decision.ticker == "HGRU11"
    assert decision.action == "APORTAR"
    assert "valuation" in decision.rationale


def test_income_plan():
    plan_result = build_income(24000, 36000)
    assert plan_result.gap == 12000
    assert plan_result.coverage_ratio == 2 / 3


def test_dividend_priority():
    result = rank_div(
        (
            DividendCandidate("B", 0.10, 0.8, 0.2, 0.1),
            DividendCandidate("A", 0.12, 0.8, 0.2, 0.1),
        )
    )
    assert result[0].ticker == "A"


def test_margin_matrix():
    result = rank_margin(
        (
            MarginPoint("B", 0.10, "DCF", 0.8),
            MarginPoint("A", 0.20, "Gordon", 0.7),
        )
    )
    assert result[0].ticker == "A"


def test_risk_budget():
    result = assess("HGRU11", 0.35, 0.30, 6)
    assert result.breach
    assert result.current_weight == 0.35


def test_allocation_plan():
    result = plan(
        (("HGRU11", 0.05), ("CPFE3", 0.10)),
        (("HGRU11", 0.10), ("CPFE3", 0.05)),
    )
    assert result[0].ticker == "HGRU11"
    assert result[0].action == "AUMENTAR"
    assert result[1].action == "REDUZIR"


def test_history():
    previous = DecisionPoint("2026-08-01", "HGRU11", "MANTER", 6)
    current = DecisionPoint("2026-08-29", "HGRU11", "APORTAR", 7)
    assert action_changed(previous, current)
    assert not action_changed(previous, previous)


def test_strategy_pipeline():
    data = StrategyPipelineInput(
        "2026-08-29",
        (sample(),),
        24000,
        36000,
        (("HGRU11", 0.05),),
        (("HGRU11", 0.10),),
    )
    report = run(data)
    assert report.contribution_candidates[0].ticker == "HGRU11"
    assert report.income_plan.gap == 12000
    assert report.allocation_needs[0].action == "AUMENTAR"


def test_strategy_e2e():
    data = StrategyPipelineInput(
        "2026-08-29",
        (sample(),),
        24000,
        36000,
        (("HGRU11", 0.05),),
        (("HGRU11", 0.10),),
    )
    result = execute(data)
    assert result.success
    assert result.report.decisions[0].action == "APORTAR"
