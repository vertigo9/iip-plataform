from iip.cycle.allocation_bridge import eligible_candidates
from iip.cycle.cycle_builder import build_cycle
from iip.cycle.decision_adapter import normalize_decision
from iip.cycle.evidence_bridge import evidence_ready
from iip.cycle.historical_bridge import HistoricalPoint, detect_action_change
from iip.cycle.income_bridge import normalize_income
from iip.cycle.models import CycleStatus, PortfolioAssetInput
from iip.cycle.pipeline import run
from iip.cycle.registry_adapter import normalize_registry_asset
from iip.cycle.report import render


def assets():
    return (
        PortfolioAssetInput(
            "HGRU11",
            "fund",
            10000,
            0.10,
            9.0,
            0.9,
            "APORTAR",
            1200,
            ("e1", "e1"),
        ),
        PortfolioAssetInput(
            "CPFE3",
            "equity",
            8000,
            0.08,
            7.5,
            0.8,
            "MANTER",
            600,
            ("e2",),
        ),
    )


def test_registry_adapter():
    class Asset:
        ticker = "hgru11"
        asset_class = "fund"
        manager = "Patria"
        segment = "Renda Urbana"
        structure = "Tijolo"

    result = normalize_registry_asset(Asset())
    assert result.ticker == "HGRU11"
    assert result.segment == "Renda Urbana"


def test_decision_normalization():
    ticker, score, confidence, action = normalize_decision(
        "cpfe3", score=12, confidence=-1, action="MANTER"
    )
    assert ticker == "CPFE3"
    assert score == 10
    assert confidence == 0
    assert action == "MANTER"


def test_income_and_evidence():
    assert normalize_income(None) == 0
    assert normalize_income(12.345678901234) == 12.345678901234
    assert evidence_ready(("e1",))
    assert not evidence_ready(())


def test_cycle_degrades_unsafe_buy_without_evidence():
    result = build_cycle(
        "c1",
        "2026-08-29",
        (PortfolioAssetInput("HGRU11", "fund", 100, 0.1, 9, 0.9, "APORTAR"),),
    )
    assert result.status == CycleStatus.DEGRADED


def test_cycle_ready_with_evidence():
    result = build_cycle("c1", "2026-08-29", assets())
    assert result.status == CycleStatus.READY
    assert result.observations[0].evidence_count == 1


def test_allocation_candidates():
    result = build_cycle("c1", "2026-08-29", assets())
    candidates = eligible_candidates(result.observations, min_score=8)
    assert len(candidates) == 1
    assert candidates[0].ticker == "HGRU11"


def test_historical_change():
    previous = HistoricalPoint("c1", "HGRU11", 8, "MANTER")
    current = HistoricalPoint("c2", "HGRU11", 9, "APORTAR")
    assert detect_action_change(previous, current)
    assert not detect_action_change(previous, previous)


def test_report():
    result = build_cycle("c1", "2026-08-29", assets())
    report = render(result, 1)
    assert report.total_assets == 2
    assert report.evidence_ready_assets == 2
    assert report.annual_income == 1800


def test_closed_loop_pipeline():
    result = run("c1", "2026-08-29", assets())
    assert result.cycle.status == CycleStatus.READY
    assert result.report.buy_candidates == 1
    assert result.report.cycle_id == "c1"
