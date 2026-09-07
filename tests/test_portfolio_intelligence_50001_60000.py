from iip.portfolio_intelligence.exposure import aggregate
from iip.portfolio_intelligence.holdings import Holding, normalize_holdings
from iip.portfolio_intelligence.income_intelligence import (
    IncomeSource,
    income_concentration,
)
from iip.portfolio_intelligence.intelligence_pipeline import build as build_snapshot
from iip.portfolio_intelligence.manager_intelligence import aggregate_manager
from iip.portfolio_intelligence.opportunity_radar import build
from iip.portfolio_intelligence.quality_radar import QualityRadar
from iip.portfolio_intelligence.risk_radar import RiskPoint, sort_risk
from iip.portfolio_intelligence.scorecard import AssetScore, PortfolioScorecard
from iip.portfolio_intelligence.segment_intelligence import aggregate_segment
from iip.portfolio_intelligence.thesis_radar import ThesisPoint, prioritize


def holdings():
    return (
        Holding("hgru11", 0.20, "fund", "Patria", "Renda Urbana", "Baixo"),
        Holding("lvbi11", 0.10, "fund", "Patria", "Logística", "Baixo"),
        Holding("cpfe3", 0.15, "equity", None, "Utilities", "Baixo"),
        Holding("schd", 0.10, "etf", None, None, None),
    )


def test_normalize_holdings():
    result = normalize_holdings(holdings())
    assert result[0].ticker == "HGRU11"
    assert result[0].weight == 0.20


def test_exposure():
    result = aggregate(holdings(), "asset_class")
    assert ("fund", 0.30) in result


def test_scorecard():
    scorecard = PortfolioScorecard(
        (
            AssetScore("HGRU11", 9, 0.9, "APORTAR"),
            AssetScore("CPFE3", 7, 0.8, "MANTER"),
        )
    )
    assert scorecard.average_score == 8
    assert scorecard.high_conviction[0].ticker == "HGRU11"


def test_income_concentration():
    result = income_concentration(
        (
            IncomeSource("HGRU11", 120, 0.2),
            IncomeSource("CPFE3", 80, 0.15),
        )
    )
    assert result[0].ticker == "HGRU11"
    assert result[0].income_share == 0.6


def test_quality_radar():
    result = QualityRadar("CPFE3", 9, 8, 8, 7)
    assert result.composite == 8


def test_thesis_prioritization():
    result = prioritize(
        (
            ThesisPoint("A", "Neutro", 4, False),
            ThesisPoint("B", "Atenção", 2, True),
        )
    )
    assert result[0].ticker == "B"


def test_risk_sort():
    result = sort_risk(
        (
            RiskPoint("A", "Médio", 0.2, 5),
            RiskPoint("B", "Alto", 0.1, 8),
        )
    )
    assert result[0].ticker == "B"


def test_opportunity_radar():
    result = build("hgru11", 9, 0.5)
    assert result.ticker == "HGRU11"
    assert result.opportunity_score == 13.5


def test_manager_and_segment():
    managers = aggregate_manager(holdings())
    segments = aggregate_segment(holdings())
    assert managers[0].manager == "Patria"
    assert managers[0].weight == 0.30
    assert segments[0].segment == "Renda Urbana"


def test_integrated_snapshot():
    snapshot = build_snapshot(
        holdings(),
        (
            AssetScore("HGRU11", 9, 0.9, "APORTAR"),
            AssetScore("CPFE3", 7, 0.8, "MANTER"),
        ),
    )
    assert len(snapshot.holdings) == 4
    assert snapshot.scorecard.high_conviction[0].ticker == "HGRU11"
    assert ("fund", 0.30) in snapshot.asset_class_exposure
