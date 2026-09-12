import json

from iip.analysis.framework import AssetData, EquityAnalyzer, FIIAnalyzer

print("=" * 60)
print("IIP ATLAS MONITOR — TEST SCRIPT")
print("=" * 60)
print()

# Teste 1: Equity Analyzer
print("[TEST 1] Equity Analyzer")
print("-" * 40)

try:
    data = AssetData(
        symbol="TESTE3.SA",
        sector="Financeiro",
        industry="Bancos",
        financials={
            "ebit": 1000000,
            "net_income": 800000,
            "revenue": 5000000,
            "equity": 10000000,
            "invested_capital": 12000000,
            "revenue_growth_3y": 10.0,
            "earnings_growth_3y": 12.0,
            "book_value_growth_3y": 8.0,
            "gross_margin_stability": 70,
            "pricing_power": 65,
            "switching_costs": 60,
            "insider_ownership": 5,
            "management_tenure_years": 8,
            "skin_in_game_ratio": 3,
            "fcf_conversion_ratio": 0.85,
            "ocf_growth_3y": 9.0,
            "capex_to_revenue": 0.15,
            "board_independence": 0.6,
            "related_party_transactions_ratio": 0.05,
            "audit_quality_score": 75,
            "dividend_yield": 6.0,
            "payout_ratio": 0.6,
            "dividend_consistency_years": 10,
            "wacc": 8.0,
            "acquisition_success_score": 55,
            "buyback_effectiveness": 60,
            "debt_to_equity": 0.4,
            "interest_coverage": 6.0,
            "current_ratio": 1.5,
        },
    )

    analyzer = EquityAnalyzer()
    report = analyzer.analyze(data)

    print(f"Asset: {report.asset_symbol}")
    print(f"Type: {report.asset_type}")
    print(f"Overall Score: {report.overall_score:.1f}/100")
    print(f"Recommendation: {report.recommendation}")
    print(f"Risk Level: {report.risk_level}")
    print()
    print("Pillar Scores:")
    for ps in report.pillar_scores:
        print(f"  - {ps.pillar.value}: {ps.score:.1f} (weight: {ps.weight})")
    print()

except Exception as e:  # noqa: BLE001 — script de diagnostico manual: captura qualquer erro pra imprimir detalhes de debug
    print("ERROR in Equity Analyzer:")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {e!s}")
    import traceback

    traceback.print_exc()

print()

# Teste 2: FII Analyzer
print("[TEST 2] FII Analyzer")
print("-" * 40)

try:
    data = AssetData(
        symbol="TESTE11.FII",
        sector="Imobiliario",
        industry="Tijolo",
        financials={
            "occupancy_rate": 0.95,
            "avg_lease_term_years": 8,
            "tenant_concentration_top5": 0.25,
            "location_quality_score": 85,
            "property_diversification_score": 75,
            "reit_premium_discount": 0.05,
            "npa_growth_3y": 12.0,
            "dividend_growth_3y": 10.0,
            "acquisitions_pipeline_value": 50,
            "management_fee_ratio": 0.004,
            "manager_track_record_years": 12,
            "assets_under_management_millions": 500,
            "distribution_ytd": 0.12,
            "distribution_consistency_months": 24,
            "reserves_to_npa": 0.08,
            "board_independence": 0.65,
            "related_party_leasing_ratio": 0.1,
            "disclosure_quality_score": 80,
            "dividend_yield": 10.5,
            "yield_on_cost": 11.0,
            "payout_sustainability_score": 85,
            "successful_acquisitions_3y": 5,
            "disposal_success_ratio": 0.7,
            "dilution_from_capital_raise": 0.02,
            "leverage_to_npa": 0.25,
            "weighted_avg_debt_maturity_years": 7,
            "fixed_debt_ratio": 0.85,
        },
    )

    analyzer = FIIAnalyzer()
    report = analyzer.analyze(data)

    print(f"Asset: {report.asset_symbol}")
    print(f"Type: {report.asset_type}")
    print(f"Overall Score: {report.overall_score:.1f}/100")
    print(f"Recommendation: {report.recommendation}")
    print(f"Risk Level: {report.risk_level}")
    print()
    print("Pillar Scores:")
    for ps in report.pillar_scores:
        print(f"  - {ps.pillar.value}: {ps.score:.1f} (weight: {ps.weight})")
    print()

except Exception as e:  # noqa: BLE001 — script de diagnostico manual: captura qualquer erro pra imprimir detalhes de debug
    print("ERROR in FII Analyzer:")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {e!s}")
    import traceback

    traceback.print_exc()

print()

# Teste 3: Export to JSON
print("[TEST 3] Export to JSON")
print("-" * 40)

try:
    data = AssetData(
        symbol="JSON3.SA",
        sector="Test",
        industry="Test",
        financials={"ebit": 1000000, "net_income": 800000, "revenue": 5000000},
    )

    analyzer = EquityAnalyzer()
    report = analyzer.analyze(data)
    report_dict = report.to_dict()

    print("Report exported as dictionary:")
    print(json.dumps(report_dict, indent=2))

except Exception as e:  # noqa: BLE001 — script de diagnostico manual: captura qualquer erro pra imprimir detalhes de debug
    print("ERROR in JSON export:")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {e!s}")

print()
print("=" * 60)
print("TEST COMPLETED")
print("=" * 60)
