from iip.analysis import Pillar
from iip.analysis.framework import AssetData


def test_agro_analyzer_creates_report():
    from iip.analysis.agro_analyzer import AgroAnalyzer

    analyzer = AgroAnalyzer()
    data = AssetData(symbol="AGRO11.FII", sector="Agricola", industry="Tijolo")
    report = analyzer.analyze(data)
    assert report.asset_symbol == "AGRO11.FII"
    assert report.asset_type == "agro"
    assert len(report.pillar_scores) == 9


def test_agro_analyzer_all_pillars_present():
    from iip.analysis.agro_analyzer import AgroAnalyzer

    analyzer = AgroAnalyzer()
    data = AssetData(symbol="ALL9.AGRO", sector="Agricola", industry="Pasto")
    report = analyzer.analyze(data)

    pillars = [ps.pillar for ps in report.pillar_scores]
    for pillar in Pillar:
        assert pillar in pillars


def test_agro_analyzer_with_sample_data():
    from iip.analysis.agro_analyzer import AgroAnalyzer

    analyzer = AgroAnalyzer()
    data = AssetData(
        symbol="SAMPLE_AGRO.FII",
        sector="Agricola",
        industry="Graneis",
        financials={
            "land_quality_score": 80,
            "crop_diversification_score": 70,
            "regional_concentration_score": 65,
            "commodity_mix_balance": 75,
            "land_appreciation_potential_score": 70,
            "water_access_quality_score": 75,
            "logistics_location_score": 65,
            "scale_advantage_score": 60,
            "yield_improvement_trend": 4.0,
            "agribusiness_experience_years": 15,
            "agronomy_team_quality_score": 75,
            "operational_efficiency_score": 72,
            "harvest_consistency_score": 78,
            "free_cash_flow_per_hectare": 800,
            "receivables_collection_rate": 0.92,
            "dividend_yield_pct": 12.0,
            "payout_ratio": 0.92,
            "seasonality_smoothing_mechanism": True,
            "distribution_frequency_months": 3,
            "crop_insurance_coverage_ratio": 0.88,
            "debt_to_assets_ratio": 0.30,
            "liquidity_reserve_months": 5,
        },
    )
    report = analyzer.analyze(data)
    assert report.overall_score > 0
    assert report.overall_score <= 100
    assert report.recommendation in ["Strong Buy", "Buy", "Hold", "Reduce", "Sell"]
