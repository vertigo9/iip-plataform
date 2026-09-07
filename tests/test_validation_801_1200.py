from iip.validation_engine.backtest import run
from iip.validation_engine.calibration import calibrate
from iip.validation_engine.hit_rate import hit_rate, regime_hit_rate
from iip.validation_engine.models import HistoricalDecision, MarketRegime
from iip.validation_engine.regime import RegimeObservation, classify
from iip.validation_engine.report import render
from iip.validation_engine.returns import ReturnPoint, max_drawdown, simple_return
from iip.validation_engine.stress import StressScenario, apply_scenario
from iip.validation_engine.temporal_score import aggregate
from iip.validation_engine.validation import summarize


def sample():
    return (
        HistoricalDecision(
            "2026-01", "HGRU11", 8.5, "APORTAR", 0.10, 0.01, MarketRegime.NORMAL
        ),
        HistoricalDecision(
            "2026-02", "HGRU11", 9.0, "APORTAR", -0.05, 0.01, MarketRegime.STRESS
        ),
        HistoricalDecision(
            "2026-01", "CPFE3", 7.5, "MANTER", 0.04, 0.02, MarketRegime.EXPANSION
        ),
        HistoricalDecision(
            "2026-02", "CPFE3", 6.5, "AGUARDAR", -0.02, 0.02, MarketRegime.NORMAL
        ),
    )


def test_simple_return_and_drawdown():
    assert simple_return(100, 110) == 0.10
    assert (
        max_drawdown(
            (
                ReturnPoint("1", 100),
                ReturnPoint("2", 120),
                ReturnPoint("3", 90),
            )
        )
        == 0.25
    )


def test_backtest():
    result = run(sample())
    assert len(result.outcomes) == 4
    assert result.max_drawdown >= 0


def test_stress_scenario():
    result = apply_scenario(
        sample(),
        StressScenario("test", -0.10, -0.01),
    )
    assert result.observations == 4
    assert result.worst_return <= -0.10


def test_regime_classification():
    assert classify(RegimeObservation("d", -0.15, 0.20)) == MarketRegime.STRESS
    assert classify(RegimeObservation("d", 0.15, 0.10)) == MarketRegime.EXPANSION
    assert classify(RegimeObservation("d", 0.02, 0.25)) == MarketRegime.NORMAL


def test_temporal_score():
    result = aggregate(sample())
    hgru = next(item for item in result if item.ticker == "HGRU11")
    assert hgru.observations == 2
    assert hgru.latest_score == 9.0


def test_hit_rate():
    result = hit_rate(sample())
    assert result == 2 / 3
    assert regime_hit_rate(sample(), MarketRegime.STRESS) == 0.0


def test_validation_summary():
    summary = summarize(sample())
    assert summary.observations == 4
    assert 0 <= summary.hit_rate <= 1


def test_calibration():
    bins = calibrate(sample())
    assert len(bins) == 4
    assert bins[-1].observations == 2


def test_report():
    text = render(summarize(sample()))
    assert "hit_rate=" in text
    assert "max_drawdown=" in text
