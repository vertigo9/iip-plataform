from iip.analysis import Pillar
from iip.analysis.framework import AssetData


def test_fixed_income_analyzer_creates_report():
    from iip.analysis.fixed_income_analyzer import FixedIncomeAnalyzer

    analyzer = FixedIncomeAnalyzer()
    data = AssetData(symbol="AXIA3", sector="Financeiro", industry="FMP-FGTS")
    report = analyzer.analyze(data)
    assert report.asset_symbol == "AXIA3"
    assert report.asset_type == "fixed_income"
    assert len(report.pillar_scores) == 9


def test_fixed_income_analyzer_all_pillars_present():
    from iip.analysis.fixed_income_analyzer import FixedIncomeAnalyzer

    analyzer = FixedIncomeAnalyzer()
    data = AssetData(symbol="AXIA3", sector="Financeiro", industry="FMP-FGTS")
    report = analyzer.analyze(data)

    pillars = [ps.pillar for ps in report.pillar_scores]
    for pillar in Pillar:
        assert pillar in pillars


def test_fixed_income_analyzer_pillar_weights_sum_to_one():
    from iip.analysis.fixed_income_analyzer import FixedIncomeAnalyzer

    analyzer = FixedIncomeAnalyzer()
    assert round(sum(analyzer.pillar_weights.values()), 6) == 1.0


def test_fixed_income_analyzer_with_sample_data():
    from iip.analysis.fixed_income_analyzer import FixedIncomeAnalyzer

    analyzer = FixedIncomeAnalyzer()
    data = AssetData(
        symbol="AXIA3",
        sector="Financeiro",
        industry="FMP-FGTS",
        financials={
            "mandate_clarity_score": 90,
            "regulatory_compliance_score": 95,
            "underlying_asset_type": "ação única",
            "exclusive_access_channel": True,
            "replacement_difficulty_score": 60,
            "assets_under_management_millions": 500,
            "cotista_growth_pct": 2,
            "net_flows_millions": 5,
            "manager_experience_years": 15,
            "management_fee_pct": 0.3,
            "redemption_frequency_days": 30,
            "redemption_restriction_score": 40,
            "avg_redemption_processing_days": 15,
            "portfolio_disclosure_frequency_days": 30,
            "disclosure_quality_score": 80,
            "distribution_yield_pct": 3,
            "distribution_frequency_per_year": 1,
            "underlying_management_quality_score": 70,
            "rebalancing_frequency_per_year": 0,
            "underlying_concentration_pct": 100,
            "nav_volatility_pct": 25,
            "underlying_credit_quality_score": 55,
        },
    )
    report = analyzer.analyze(data)
    assert report.overall_score > 0
    assert report.overall_score <= 100
    assert report.recommendation in ["Strong Buy", "Buy", "Hold", "Reduce", "Sell"]


def test_fixed_income_analyzer_high_concentration_hurts_resilience():
    from iip.analysis.fixed_income_analyzer import FixedIncomeAnalyzer

    analyzer = FixedIncomeAnalyzer()
    concentrado = AssetData(
        symbol="AXIA3",
        sector="Financeiro",
        industry="FMP-FGTS",
        financials={"underlying_concentration_pct": 100, "nav_volatility_pct": 40},
    )
    diversificado = AssetData(
        symbol="DIVERSO3",
        sector="Financeiro",
        industry="Multiativos",
        financials={"underlying_concentration_pct": 10, "nav_volatility_pct": 5},
    )
    report_concentrado = analyzer.analyze(concentrado)
    report_diversificado = analyzer.analyze(diversificado)

    resilience_concentrado = next(
        p for p in report_concentrado.pillar_scores if p.pillar == Pillar.RESILIENCE
    )
    resilience_diversificado = next(
        p for p in report_diversificado.pillar_scores if p.pillar == Pillar.RESILIENCE
    )
    assert resilience_concentrado.score < resilience_diversificado.score


def test_fixed_income_analyzer_restricted_redemption_hurts_cash_flow():
    from iip.analysis.fixed_income_analyzer import FixedIncomeAnalyzer

    analyzer = FixedIncomeAnalyzer()
    restrito = AssetData(
        symbol="AXIA3",
        sector="Financeiro",
        industry="FMP-FGTS",
        financials={
            "redemption_frequency_days": 365,
            "redemption_restriction_score": 10,
            "avg_redemption_processing_days": 90,
        },
    )
    report = analyzer.analyze(restrito)
    cash_flow = next(p for p in report.pillar_scores if p.pillar == Pillar.CASH_FLOW)
    assert cash_flow.score < 30
