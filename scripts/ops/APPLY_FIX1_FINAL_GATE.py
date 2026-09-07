from pathlib import Path

path = Path("tests/test_final_gate_540001_580000.py")
if not path.exists():
    raise SystemExit(f"Arquivo não encontrado: {path}")

content = r"""
import pytest

from iip.benchmark.drawdown import worst_drawdown
from iip.benchmark.models import BenchmarkPoint, BenchmarkSeries, BenchmarkType
from iip.benchmark.performance import compare as benchmark_compare, series_return
from iip.benchmark.risk_adjusted import sharpe_like, volatility
from iip.hardening.compatibility import compare_keys
from iip.hardening.contracts import check_nonempty, check_version
from iip.hardening.persistence import PersistedState, next_revision
from iip.hardening.provider_failover import ProviderState, choose_provider
from iip.universal.contribution_policy import ContributionRule, evaluate
from iip.validation_engine.backtest import run as backtest_run
from iip.validation_engine.models import HistoricalDecision


def test_benchmark_performance_paths():
    asset = BenchmarkSeries(
        "Asset",
        BenchmarkType.CDI,
        (BenchmarkPoint("d1", 100.0), BenchmarkPoint("d2", 110.0)),
    )
    benchmark = BenchmarkSeries(
        "CDI",
        BenchmarkType.CDI,
        (BenchmarkPoint("d1", 100.0), BenchmarkPoint("d2", 105.0)),
    )
    assert series_return(asset) == pytest.approx(0.10)
    assert series_return(BenchmarkSeries("one", BenchmarkType.CDI, (BenchmarkPoint("d", 1),))) == 0.0

    result = benchmark_compare("cpfe3", asset, benchmark)
    assert result.ticker == "CPFE3"
    assert result.excess_return == pytest.approx(0.05)


def test_benchmark_drawdown_and_risk_adjusted_paths():
    assert worst_drawdown(()) .drawdown == 0.0
    diagnostic = worst_drawdown((100.0, 120.0, 90.0, 110.0))
    assert diagnostic.peak_value == 120.0
    assert diagnostic.trough_value == 90.0
    assert diagnostic.drawdown == pytest.approx(0.25)

    assert volatility(()) == 0.0
    assert volatility((0.1,)) == 0.0
    vol = volatility((0.01, 0.02, 0.03))
    assert vol > 0
    assert sharpe_like(()) == 0.0
    assert sharpe_like((0.02, 0.02)) == 0.0
    assert sharpe_like((0.01, 0.02, 0.03), risk_free=0.01) > 0


def test_hardening_compatibility_contract_and_persistence():
    compatible = compare_keys(("a", "b"), ("a", "b", "c"))
    assert compatible.compatible
    assert compatible.missing == ()
    assert compatible.extra == ("c",)

    incompatible = compare_keys(("a", "b"), ("a",))
    assert not incompatible.compatible
    assert incompatible.missing == ("b",)

    assert check_nonempty("x", "ok").passed
    assert not check_nonempty("x", "").passed
    assert check_version(3, 2).passed
    assert not check_version(1, 2).passed

    first = next_revision(None, "h1", {"x": 1})
    second = next_revision(first, "h2", {"x": 2})
    assert isinstance(first, PersistedState)
    assert first.revision == 1
    assert second.revision == 2
    assert second.key == first.key


def test_provider_failover_selection():
    states = (
        ProviderState("zeta", True, 5),
        ProviderState("alpha", True, 2),
        ProviderState("beta", False, 1),
    )
    chosen = choose_provider(states)
    assert chosen is not None
    assert chosen.name == "alpha"
    assert choose_provider(()) is None


def test_contribution_policy_all_branches():
    rule = ContributionRule(7.0, 0.70, 0.20)

    assert evaluate("A", 6.9, 0.9, 0.1, rule).reason == "score_below_minimum"
    assert evaluate("A", 7.0, 0.69, 0.1, rule).reason == "confidence_below_minimum"
    assert evaluate("A", 7.0, 0.70, 0.20, rule).reason == "position_above_limit"

    decision = evaluate("A", 7.0, 0.70, 0.19, rule)
    assert decision.eligible
    assert decision.reason == "eligible"


def test_backtest_empty_and_realized_paths():
    assert backtest_run(()).cumulative_return == 0.0
    decisions = (
        HistoricalDecision("d1", "A", 8.0, "COMPRAR", 0.10, 1.0),
        HistoricalDecision("d2", "B", 7.0, "MANTER", None, 2.0),
        HistoricalDecision("d3", "C", 6.0, "MANTER", -0.05, None),
    )
    result = backtest_run(decisions)
    assert len(result.outcomes) == 2
    assert result.outcomes[0].realized_income == 1.0
    assert result.outcomes[1].realized_income == 0.0
    assert result.max_drawdown >= 0


def test_validation_return_boundaries():
    from iip.validation_engine.returns import cumulative_return, max_drawdown, simple_return, ReturnPoint

    assert simple_return(100, 100) == 0.0
    assert cumulative_return(()) == 0.0
    assert max_drawdown(()) == 0.0
    with pytest.raises(ValueError):
        simple_return(0, 1)
    points = (ReturnPoint("a", 100), ReturnPoint("b", 80))
    assert cumulative_return(points) == pytest.approx(-0.20)
    assert max_drawdown(points) == pytest.approx(0.20)


def test_valuation_and_decision_validation_edges():
    from iip.decision.models import Decision, EvidenceRef, Verdict
    from iip.decision.validation import validate_decision
    from iip.decision.valuation_bridge import ValuationSnapshot, valuation_score

    assert valuation_score(ValuationSnapshot("A")) == 5.0
    assert valuation_score(ValuationSnapshot("A", 120.0, 0.0)) == 0.0
    assert valuation_score(ValuationSnapshot("A", 120.0, 100.0)) == 7.0

    missing = Decision("A", Verdict.MANTER, 5.0, 0.8, ("r",))
    assert not validate_decision(missing).valid

    good = Decision(
        "A",
        Verdict.MANTER,
        8.0,
        0.8,
        ("r",),
        (EvidenceRef("EV-1"),),
    )
    assert validate_decision(good).valid

    bad_score = Decision(
        "A",
        Verdict.MANTER,
        11.0,
        0.8,
        ("r",),
        (EvidenceRef("EV-1"),),
    )
    assert "score_out_of_range" in validate_decision(bad_score).reasons
""".strip()

path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
print("FIX1_FINAL_GATE aplicado com APIs confirmadas.")
