from iip.analysis import Pillar
from iip.analysis.framework import AssetData


def test_infra_analyzer_creates_report():
    from iip.analysis.infra_analyzer import InfraAnalyzer

    analyzer = InfraAnalyzer()
    data = AssetData(symbol="INFRA11.SA", sector="Energia", industry="Transmissao")
    report = analyzer.analyze(data)
    assert report.asset_symbol == "INFRA11.SA"
    assert report.asset_type == "infra"
    assert len(report.pillar_scores) == 9


def test_infra_analyzer_all_pillars_present():
    from iip.analysis.infra_analyzer import InfraAnalyzer

    analyzer = InfraAnalyzer()
    data = AssetData(symbol="ALL9.INFRA", sector="Infra", industry="Logistica")
    report = analyzer.analyze(data)

    pillars = [ps.pillar for ps in report.pillar_scores]
    for pillar in Pillar:
        assert pillar in pillars


def test_infra_analyzer_with_sample_data():
    from iip.analysis.infra_analyzer import InfraAnalyzer

    analyzer = InfraAnalyzer()
    data = AssetData(
        symbol="SAMPLE_INFRA.SA",
        sector="Energia",
        industry="Transmissao",
        financials={
            "revenue_stability_score": 85,
            "concession_remaining_years": 18,
            "regulatory_environment_score": 75,
            "sector_type": "transmission",
            "market_share_percentage": 65,
            "customer_switching_cost_score": 80,
            "entry_barrier_score": 90,
            "geographic_monopoly_status": True,
            "cash_flow_predictability_score": 88,
            "ebitda_to_fcf_conversion": 0.85,
            "operating_margin_ebitda": 0.65,
            "free_cash_flow_yield_pct": 9.5,
            "dividend_yield_pct": 12.5,
            "mandatory_payout_ratio": 0.95,
            "distribution_consistency_score": 90,
        },
    )
    report = analyzer.analyze(data)
    assert report.overall_score > 0
    assert report.overall_score <= 100
    assert report.recommendation in ["Strong Buy", "Buy", "Hold", "Reduce", "Sell"]
