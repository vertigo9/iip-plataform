from pathlib import Path

path = Path("tests/test_final_gate_540001_580000.py")
if not path.exists():
    raise SystemExit(f"Arquivo não encontrado: {path}")

content = r"""
import pytest

from iip.benchmark.models import BenchmarkPoint, BenchmarkSeries, BenchmarkType
from iip.benchmark.performance import compare, series_return
from iip.benchmark.risk_adjusted import sharpe_like, volatility
from iip.hardening.compatibility import compare_keys
from iip.hardening.contracts import check_nonempty, check_version
from iip.hardening.persistence import PersistedState, next_revision
from iip.hardening.provider_failover import ProviderState, choose_provider
from iip.universal.contribution_policy import ContributionRule, evaluate
from iip.validation_engine.backtest import run as backtest_run
from iip.validation_engine.models import HistoricalDecision
from iip.decision.models import Decision, EvidenceRef, Verdict
from iip.decision.validation import validate_decision
from iip.decision.valuation_bridge import ValuationSnapshot, valuation_score


def test_benchmark_performance_all_paths():
    one = BenchmarkSeries(
        "ONE",
        BenchmarkType.CDI,
        (BenchmarkPoint("d1", 100.0),),
    )
    asset = BenchmarkSeries(
        "ASSET",
        BenchmarkType.CDI,
        (BenchmarkPoint("d1", 100.0), BenchmarkPoint("d2", 110.0)),
    )
    bench = BenchmarkSeries(
        "BENCH",
        BenchmarkType.CDI,
        (BenchmarkPoint("d1", 100.0), BenchmarkPoint("d2", 105.0)),
    )

    assert series_return(one) == 0.0
    assert series_return(asset) == pytest.approx(0.10)

    result = compare("cpfe3", asset, bench)
    assert result.ticker == "CPFE3"
    assert result.asset_return == pytest.approx(0.10)
    assert result.benchmark_return == pytest.approx(0.05)
    assert result.excess_return == pytest.approx(0.05)


def test_benchmark_risk_adjusted_all_paths():
    assert volatility(()) == 0.0
    assert volatility((0.10,)) == 0.0

    vol = volatility((0.01, 0.02, 0.03))
    assert vol > 0

    assert sharpe_like(()) == 0.0
    assert sharpe_like((0.02, 0.02)) == 0.0
    assert sharpe_like((0.01, 0.02, 0.03), risk_free=0.01) > 0


def test_hardening_compatibility_contract():
    compatible = compare_keys(("a", "b"), ("a", "b", "c"))
    assert compatible.compatible
    assert compatible.missing == ()
    assert compatible.extra == ("c",)

    incompatible = compare_keys(("a", "b"), ("a",))
    assert not incompatible.compatible
    assert incompatible.missing == ("b",)
    assert incompatible.extra == ()

    assert check_nonempty("field", "value").passed
    assert check_nonempty("field", "").passed is False
    assert check_version(3, 2).passed
    assert check_version(1, 2).passed is False


def test_hardening_persistence_and_failover():
    first = next_revision(None, "h1", {"x": 1})
    second = next_revision(first, "h2", {"x": 2})

    assert isinstance(first, PersistedState)
    assert first.revision == 1
    assert second.revision == 2
    assert second.key == first.key

    states = (
        ProviderState("zeta", True, 5),
        ProviderState("alpha", True, 2),
        ProviderState("beta", False, 1),
    )
    assert choose_provider(states).name == "alpha"
    assert choose_provider(()) is None


def test_contribution_policy_all_branches():
    rule = ContributionRule(7.0, 0.70, 0.20)

    assert evaluate("A", 6.9, 0.9, 0.10, rule).reason == "score_below_minimum"
    assert evaluate("A", 7.0, 0.69, 0.10, rule).reason == "confidence_below_minimum"
    assert evaluate("A", 7.0, 0.70, 0.20, rule).reason == "position_above_limit"

    eligible = evaluate("A", 7.0, 0.70, 0.19, rule)
    assert eligible.eligible
    assert eligible.reason == "eligible"


def test_backtest_paths():
    assert backtest_run(()).cumulative_return == 0.0

    decisions = (
        HistoricalDecision("A", "A", 8.0, "COMPRAR", 0.10, 1.0),
        HistoricalDecision("B", "B", 7.0, "MANTER", None, 2.0),
        HistoricalDecision("C", "C", 6.0, "MANTER", -0.05, None),
    )
    result = backtest_run(decisions)

    assert len(result.outcomes) == 2
    assert result.outcomes[0].realized_income == 1.0
    assert result.outcomes[1].realized_return == pytest.approx(-0.05)
    assert result.max_drawdown >= 0.0


def test_decision_validation_and_valuation_edges():
    missing = Decision("A", Verdict.MANTER, 5.0, 0.8, ("r",))
    assert not validate_decision(missing).valid
    assert "missing_evidence" in validate_decision(missing).reasons

    good = Decision(
        "A",
        Verdict.MANTER,
        8.0,
        0.8,
        ("r",),
        (EvidenceRef("EV-1"),),
    )
    assert validate_decision(good).valid

    low_buy_confidence = Decision(
        "A",
        Verdict.COMPRAR,
        8.0,
        0.20,
        ("r",),
        (EvidenceRef("EV-1"),),
    )
    result = validate_decision(low_buy_confidence)
    assert "low_confidence_for_buy" in result.reasons

    bad_score = Decision(
        "A",
        Verdict.MANTER,
        11.0,
        0.8,
        ("r",),
        (EvidenceRef("EV-1"),),
    )
    assert "score_out_of_range" in validate_decision(bad_score).reasons

    assert valuation_score(ValuationSnapshot("A")) == 5.0
    assert valuation_score(
        ValuationSnapshot("A", fair_value=120.0, market_price=0.0)
    ) == 0.0
    assert valuation_score(
        ValuationSnapshot("A", fair_value=120.0, market_price=100.0)
    ) == 7.0
    assert valuation_score(
        ValuationSnapshot("A", fair_value=80.0, market_price=100.0)
    ) == 3.0
""".strip()

path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
print("FIX2 aplicado: Final Gate alinhado às APIs reais do snapshot.")
