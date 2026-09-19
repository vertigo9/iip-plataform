from iip.analysis import Pillar
from iip.analysis.framework import AssetData


def test_etf_analyzer_creates_report():
    from iip.analysis.etf_analyzer import ETFAnalyzer

    analyzer = ETFAnalyzer()
    data = AssetData(symbol="BOVA11", sector="Renda Variável", industry="Índice Amplo")
    report = analyzer.analyze(data)
    assert report.asset_symbol == "BOVA11"
    assert report.asset_type == "etf"
    assert len(report.pillar_scores) == 9


def test_etf_analyzer_all_pillars_present():
    from iip.analysis.etf_analyzer import ETFAnalyzer

    analyzer = ETFAnalyzer()
    data = AssetData(symbol="IVVB11", sector="Renda Variável", industry="S&P 500")
    report = analyzer.analyze(data)

    pillars = [ps.pillar for ps in report.pillar_scores]
    for pillar in Pillar:
        assert pillar in pillars


def test_etf_analyzer_pillar_weights_sum_to_one():
    from iip.analysis.etf_analyzer import ETFAnalyzer

    analyzer = ETFAnalyzer()
    assert round(sum(analyzer.pillar_weights.values()), 6) == 1.0


def test_etf_analyzer_with_sample_data():
    from iip.analysis.etf_analyzer import ETFAnalyzer

    analyzer = ETFAnalyzer()
    data = AssetData(
        symbol="BOVA11",
        sector="Renda Variável",
        industry="Índice Amplo",
        financials={
            "index_methodology_quality_score": 90,
            "replication_method": "physical",
            "index_provider_reputation_score": 85,
            "index_uniqueness_score": 40,
            "first_mover_status": True,
            "competing_etfs_count": 2,
            "aum_millions": 15000,
            "net_inflows_ytd_millions": 500,
            "aum_growth_3y_pct": 20,
            "expense_ratio_pct": 0.28,
            "manager_etf_experience_years": 20,
            "securities_lending_revenue_share_pct": 70,
            "avg_daily_volume_brl": 80_000_000,
            "avg_bid_ask_spread_bps": 5,
            "market_makers_count": 6,
            "portfolio_disclosure_frequency_days": 1,
            "disclosure_quality_score": 90,
            "securities_lending_policy_transparency_score": 85,
            "dividend_yield_pct": 6.5,
            "distribution_frequency_per_year": 4,
            "distribution_consistency_score": 88,
            "creation_redemption_efficiency_score": 90,
            "rebalancing_cost_bps": 3,
            "in_kind_creation_ratio": 0.95,
            "tracking_error_pct": 0.15,
            "tracking_difference_pct": 0.05,
            "premium_discount_volatility_pct": 0.05,
        },
    )
    report = analyzer.analyze(data)
    assert report.overall_score > 0
    assert report.overall_score <= 100
    assert report.recommendation in ["Strong Buy", "Buy", "Hold", "Reduce", "Sell"]


def test_etf_analyzer_low_liquidity_hurts_cash_flow_pillar():
    from iip.analysis.etf_analyzer import ETFAnalyzer

    analyzer = ETFAnalyzer()
    illiquid = AssetData(
        symbol="ILLIQUID11",
        sector="Nicho",
        industry="Setorial",
        financials={
            "avg_daily_volume_brl": 1000,
            "avg_bid_ask_spread_bps": 300,
            "market_makers_count": 0,
        },
    )
    report = analyzer.analyze(illiquid)
    cash_flow = next(p for p in report.pillar_scores if p.pillar == Pillar.CASH_FLOW)
    assert cash_flow.score < 30


def test_etf_analyzer_high_tracking_error_hurts_resilience_pillar():
    from iip.analysis.etf_analyzer import ETFAnalyzer

    analyzer = ETFAnalyzer()
    bad_tracker = AssetData(
        symbol="BADTRACK11",
        sector="Renda Variável",
        industry="Setorial",
        financials={
            "tracking_error_pct": 3.0,
            "tracking_difference_pct": 2.5,
            "premium_discount_volatility_pct": 1.5,
        },
    )
    report = analyzer.analyze(bad_tracker)
    resilience = next(p for p in report.pillar_scores if p.pillar == Pillar.RESILIENCE)
    assert resilience.score < 30


def test_etf_analyzer_low_expense_ratio_helps_management_pillar():
    from iip.analysis.etf_analyzer import ETFAnalyzer

    analyzer = ETFAnalyzer()
    cheap = AssetData(
        symbol="CHEAP11",
        sector="Renda Variável",
        industry="Índice Amplo",
        financials={"expense_ratio_pct": 0.1},
    )
    expensive = AssetData(
        symbol="EXPENSIVE11",
        sector="Renda Variável",
        industry="Índice Amplo",
        financials={"expense_ratio_pct": 2.5},
    )
    cheap_report = analyzer.analyze(cheap)
    expensive_report = analyzer.analyze(expensive)

    cheap_mgmt = next(
        p for p in cheap_report.pillar_scores if p.pillar == Pillar.MANAGEMENT
    )
    expensive_mgmt = next(
        p for p in expensive_report.pillar_scores if p.pillar == Pillar.MANAGEMENT
    )
    assert cheap_mgmt.score > expensive_mgmt.score
