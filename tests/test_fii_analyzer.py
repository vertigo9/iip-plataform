from iip.analysis import Pillar
from iip.analysis.framework import AssetData, FIIAnalyzer


def test_fii_analyzer_creates_report():
    analyzer = FIIAnalyzer()
    data = AssetData(symbol="HGLG11.SA", sector="Imobiliário", industry="Shoppings")
    report = analyzer.analyze(data)
    assert report.asset_symbol == "HGLG11.SA"
    assert report.asset_type == "fii"
    assert len(report.pillar_scores) == 9


def test_fii_analyzer_all_pillars_present():
    analyzer = FIIAnalyzer()
    data = AssetData(symbol="ALL9.FII", sector="Imobiliário", industry="Lajes")
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


def test_fii_analyzer_with_sample_data():
    analyzer = FIIAnalyzer()
    data = AssetData(
        symbol="SAMPLE11.FII",
        sector="Imobiliário",
        industry="Tijolo",
        financials={
            "occupancy_rate": 0.95,
            "avg_lease_term_years": 8,
            "tenant_concentration_top5": 0.25,
            "dividend_yield": 10.5,
        },
    )
    report = analyzer.analyze(data)
    assert report.overall_score > 0
    assert report.overall_score <= 100
