from iip.analysis import Pillar
from iip.analysis.framework import AssetData, EquityAnalyzer


def test_equity_analyzer_creates_report():
    analyzer = EquityAnalyzer()
    data = AssetData(symbol="TEST3.SA", sector="Test", industry="Test")
    report = analyzer.analyze(data)
    assert report.asset_symbol == "TEST3.SA"
    assert report.asset_type == "equity"
    assert len(report.pillar_scores) == 9


def test_equity_analyzer_all_pillars_present():
    analyzer = EquityAnalyzer()
    data = AssetData(symbol="ALL9.SA", sector="Test", industry="Test")
    report = analyzer.analyze(data)

    pillars = [ps.pillar for ps in report.pillar_scores]
    assert Pillar.BUSINESS_MODEL in pillars
    assert Pillar.MOAT in pillars
    assert Pillar.GROWTH in pillars
    assert Pillar.MANAGEMENT in pillars
    assert Pillar.CASH_FLOW in pillars
    assert Pillar.GOVERNANCE in pillars
    assert Pillar.DIVIDENDS in pillars
    assert Pillar.CAPITAL_ALLOCATION in pillars
    assert Pillar.RESILIENCE in pillars


def test_equity_analyzer_with_sample_data():
    analyzer = EquityAnalyzer()
    data = AssetData(
        symbol="SAMPLE3.SA",
        sector="Financeiro",
        industry="Bancos",
        financials={
            "ebit": 1000000,
            "net_income": 800000,
            "revenue": 5000000,
            "equity": 10000000,
            "invested_capital": 12000000,
        },
    )
    report = analyzer.analyze(data)
    assert report.overall_score > 0
    assert report.overall_score <= 100


def test_calc_roic_helper():
    roic = EquityAnalyzer.calc_roic(ebit=1000000, invested_capital=10000000)
    assert roic == 10.0


def test_calc_roe_helper():
    roe = EquityAnalyzer.calc_roe(net_income=1000000, equity=10000000)
    assert roe == 10.0


def test_calc_margin_helper():
    margin = EquityAnalyzer.calc_margin(ebit=1000000, revenue=5000000)
    assert margin == 20.0
