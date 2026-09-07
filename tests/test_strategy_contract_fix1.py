from iip.strategy.income_plan import build
from iip.strategy.models import StrategyInput
from iip.strategy.strategy_engine import decide


def sample():
    return StrategyInput("HGRU11", 9, 0.9, 0.08, 0.20, 3, 0.05, 0.10)


def test_underweight_high_quality_asset_is_contribution_candidate():
    decision = decide(sample())
    assert decision.ticker == "HGRU11"
    assert decision.action == "APORTAR"
    assert decision.priority_score == 6.01


def test_income_coverage_preserves_native_ratio():
    plan_result = build(24000, 36000)
    assert plan_result.gap == 12000
    assert plan_result.coverage_ratio == 2 / 3


def test_zero_target_income_has_full_coverage():
    assert build(100, 0).coverage_ratio == 1.0
