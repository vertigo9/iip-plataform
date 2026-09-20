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


def _business_model_score(**financials):
    data = AssetData(
        symbol="TEST11",
        sector="Imobiliário",
        industry="Logística",
        financials=financials,
    )
    report = FIIAnalyzer().analyze(data)
    return next(
        p for p in report.pillar_scores if p.pillar == Pillar.BUSINESS_MODEL
    ).score


def test_fii_lease_term_stops_adding_points_after_ten_years():
    base = {"occupancy_rate": 0.6, "tenant_concentration_top5": 0.3}

    ten = _business_model_score(**base, avg_lease_term_years=10)
    thirteen = _business_model_score(**base, avg_lease_term_years=13.41)

    assert thirteen == ten


def test_fii_lease_term_still_counts_ten_points_per_year_below_the_cap():
    base = {"occupancy_rate": 0.6, "tenant_concentration_top5": 0.3}

    five = _business_model_score(**base, avg_lease_term_years=5)
    six = _business_model_score(**base, avg_lease_term_years=6)

    assert round(six - five, 2) == round(10 / 3, 2)


def test_fii_lease_term_indicator_keeps_the_real_value():
    data = AssetData(
        symbol="TEST11",
        sector="Imobiliário",
        industry="Logística",
        financials={"avg_lease_term_years": 13.41},
    )
    report = FIIAnalyzer().analyze(data)
    pillar = next(p for p in report.pillar_scores if p.pillar == Pillar.BUSINESS_MODEL)

    assert pillar.indicators["Avg Lease Term"] == 13.41
