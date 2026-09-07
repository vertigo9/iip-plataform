#!/usr/bin/env python3
"""IIP Atlas Monitor — Exemplos Práticos com Dados Reais Simulados"""

import json
from datetime import datetime

from iip.analysis.agro_analyzer import AgroAnalyzer
from iip.analysis.framework import AssetData, EquityAnalyzer, FIIAnalyzer
from iip.analysis.infra_analyzer import InfraAnalyzer


def create_equity_examples():
    """Exemplos de análise de ações B3."""
    print("=" * 70)
    print("ANÁLISE DE AÇÕES B3 — EQUITY ANALYZER")
    print("=" * 70)
    print()

    # PETR4.SA — Petrobras
    petr4 = AssetData(
        symbol="PETR4.SA",
        sector="Petróleo e Gás",
        industry="Exploração e Refino",
        financials={
            "ebit": 52000000000,
            "net_income": 41000000000,
            "revenue": 470000000000,
            "equity": 410000000000,
            "invested_capital": 520000000000,
            "revenue_growth_3y": 8.5,
            "earnings_growth_3y": 12.0,
            "book_value_growth_3y": 7.0,
            "gross_margin_stability": 65,
            "pricing_power": 60,
            "switching_costs": 55,
            "insider_ownership": 3,
            "management_tenure_years": 6,
            "skin_in_game_ratio": 2,
            "fcf_conversion_ratio": 0.82,
            "ocf_growth_3y": 7.5,
            "capex_to_revenue": 0.20,
            "board_independence": 0.55,
            "related_party_transactions_ratio": 0.03,
            "audit_quality_score": 72,
            "dividend_yield": 9.5,
            "payout_ratio": 0.75,
            "dividend_consistency_years": 8,
            "wacc": 9.0,
            "acquisition_success_score": 50,
            "buyback_effectiveness": 55,
            "debt_to_equity": 0.45,
            "interest_coverage": 5.5,
            "current_ratio": 1.4,
        },
    )

    # VALE3.SA — Vale
    vale3 = AssetData(
        symbol="VALE3.SA",
        sector="Materiais Básicos",
        industry="Mineração",
        financials={
            "ebit": 85000000000,
            "net_income": 72000000000,
            "revenue": 380000000000,
            "equity": 420000000000,
            "invested_capital": 480000000000,
            "revenue_growth_3y": -2.0,
            "earnings_growth_3y": -5.0,
            "book_value_growth_3y": 3.0,
            "gross_margin_stability": 70,
            "pricing_power": 75,
            "switching_costs": 60,
            "insider_ownership": 8,
            "management_tenure_years": 10,
            "skin_in_game_ratio": 5,
            "fcf_conversion_ratio": 0.78,
            "ocf_growth_3y": -3.0,
            "capex_to_revenue": 0.15,
            "board_independence": 0.65,
            "related_party_transactions_ratio": 0.02,
            "audit_quality_score": 78,
            "dividend_yield": 11.0,
            "payout_ratio": 0.80,
            "dividend_consistency_years": 5,
            "wacc": 8.5,
            "acquisition_success_score": 65,
            "buyback_effectiveness": 70,
            "debt_to_equity": 0.30,
            "interest_coverage": 8.0,
            "current_ratio": 1.8,
        },
    )

    # ITUB4.SA — Itaú Unibanco
    itub4 = AssetData(
        symbol="ITUB4.SA",
        sector="Financeiro",
        industry="Bancos",
        financials={
            "ebit": 45000000000,
            "net_income": 36000000000,
            "revenue": 180000000000,
            "equity": 180000000000,
            "invested_capital": 200000000000,
            "revenue_growth_3y": 6.0,
            "earnings_growth_3y": 9.0,
            "book_value_growth_3y": 7.5,
            "gross_margin_stability": 75,
            "pricing_power": 70,
            "switching_costs": 80,
            "insider_ownership": 15,
            "management_tenure_years": 12,
            "skin_in_game_ratio": 8,
            "fcf_conversion_ratio": 0.88,
            "ocf_growth_3y": 8.0,
            "capex_to_revenue": 0.08,
            "board_independence": 0.70,
            "related_party_transactions_ratio": 0.01,
            "audit_quality_score": 82,
            "dividend_yield": 7.5,
            "payout_ratio": 0.60,
            "dividend_consistency_years": 15,
            "wacc": 10.0,
            "acquisition_success_score": 75,
            "buyback_effectiveness": 60,
            "debt_to_equity": 0.20,
            "interest_coverage": 12.0,
            "current_ratio": 1.5,
        },
    )

    analyzer = EquityAnalyzer()

    for stock in [petr4, vale3, itub4]:
        report = analyzer.analyze(stock)
        print(f"{report.asset_symbol} — {stock.industry}")
        print("-" * 70)
        print(f"  Score Global: {report.overall_score:.1f}/100")
        print(f"  Recomendação: {report.recommendation}")
        print(f"  Nível de Risco: {report.risk_level}")
        print()
        print("  Top 3 Pilares Fortes:")
        sorted_pillars = sorted(
            report.pillar_scores, key=lambda x: x.score, reverse=True
        )[:3]
        for ps in sorted_pillars:
            print(f"    • {ps.pillar.value.replace('_', ' ').title()}: {ps.score:.1f}")
        print()
        print("  Pilares que Merecem Atenção:")
        weak_pillars = [ps for ps in report.pillar_scores if ps.score < 50]
        if weak_pillars:
            for ps in weak_pillars:
                print(
                    f"    • {ps.pillar.value.replace('_', ' ').title()}: {ps.score:.1f}"
                )
        else:
            print("    • Nenhum pilar crítico identificado")
        print()


def create_fii_examples():
    """Exemplos de análise de Fundos Imobiliários."""
    print("=" * 70)
    print("ANÁLISE DE FUNDOS IMOBILIÁRIOS — FII ANALYZER")
    print("=" * 70)
    print()

    # HGLG11.SA — CSHG Logística
    hlgg11 = AssetData(
        symbol="HGLG11.SA",
        sector="Imobiliário",
        industry="Logística",
        financials={
            "occupancy_rate": 0.97,
            "avg_lease_term_years": 9,
            "tenant_concentration_top5": 0.25,
            "location_quality_score": 85,
            "property_diversification_score": 75,
            "reit_premium_discount": 0.02,
            "npa_growth_3y": 12.0,
            "dividend_growth_3y": 10.0,
            "acquisitions_pipeline_value": 500,
            "management_fee_ratio": 0.004,
            "manager_track_record_years": 15,
            "assets_under_management_millions": 3500,
            "distribution_ytd": 0.115,
            "distribution_consistency_months": 36,
            "reserves_to_npa": 0.08,
            "board_independence": 0.65,
            "related_party_leasing_ratio": 0.05,
            "disclosure_quality_score": 85,
            "dividend_yield": 10.5,
            "yield_on_cost": 11.0,
            "payout_sustainability_score": 88,
            "successful_acquisitions_3y": 8,
            "disposal_success_ratio": 0.80,
            "dilution_from_capital_raise": 0.01,
            "leverage_to_npa": 0.25,
            "weighted_avg_debt_maturity_years": 7,
            "fixed_debt_ratio": 0.85,
        },
    )

    # MXRF11.SA — Maxi Renda
    mxrf11 = AssetData(
        symbol="MXRF11.SA",
        sector="Imobiliário",
        industry="Híbrido",
        financials={
            "occupancy_rate": 0.95,
            "avg_lease_term_years": 5,
            "tenant_concentration_top5": 0.40,
            "location_quality_score": 75,
            "property_diversification_score": 85,
            "reit_premium_discount": 0.05,
            "npa_growth_3y": 15.0,
            "dividend_growth_3y": 12.0,
            "acquisitions_pipeline_value": 300,
            "management_fee_ratio": 0.006,
            "manager_track_record_years": 10,
            "assets_under_management_millions": 2200,
            "distribution_ytd": 0.125,
            "distribution_consistency_months": 24,
            "reserves_to_npa": 0.05,
            "board_independence": 0.60,
            "related_party_leasing_ratio": 0.10,
            "disclosure_quality_score": 80,
            "dividend_yield": 12.5,
            "yield_on_cost": 13.0,
            "payout_sustainability_score": 82,
            "successful_acquisitions_3y": 12,
            "disposal_success_ratio": 0.75,
            "dilution_from_capital_raise": 0.03,
            "leverage_to_npa": 0.30,
            "weighted_avg_debt_maturity_years": 5,
            "fixed_debt_ratio": 0.75,
        },
    )

    analyzer = FIIAnalyzer()

    for fii in [hlgg11, mxrf11]:
        report = analyzer.analyze(fii)
        print(f"{report.asset_symbol} — {fii.industry}")
        print("-" * 70)
        print(f"  Score Global: {report.overall_score:.1f}/100")
        print(f"  Recomendação: {report.recommendation}")
        print(f"  Nível de Risco: {report.risk_level}")
        print(f"  Dividend Yield: {fii.financials['dividend_yield']}%")
        print()
        print("  Destaque Principal:")
        top_pillar = max(report.pillar_scores, key=lambda x: x.score)
        print(
            f"    • {top_pillar.pillar.value.replace('_', ' ').title()}: {top_pillar.score:.1f}"
        )
        print()


def create_infra_examples():
    """Exemplos de análise de Fundos de Infraestrutura."""
    print("=" * 70)
    print("ANÁLISE DE FUNDOS DE INFRAESTRUTURA — INFRA ANALYZER")
    print("=" * 70)
    print()

    # BTLG11.SA — BTG Pactual Logística (simulado como Infra)
    btlg11 = AssetData(
        symbol="BTLG11.SA",
        sector="Infraestrutura",
        industry="Logística",
        financials={
            "revenue_stability_score": 82,
            "concession_remaining_years": 20,
            "regulatory_environment_score": 78,
            "sector_type": "logistics",
            "market_share_percentage": 45,
            "customer_switching_cost_score": 75,
            "entry_barrier_score": 85,
            "geographic_monopoly_status": False,
            "capex_expansion_pipeline_millions": 800,
            "tariff_indexation_clause": True,
            "expansion_projects_count": 5,
            "demand_growth_forecast_5y": 4.5,
            "management_infra_experience_years": 18,
            "project_completion_rate": 0.90,
            "mgmt_asset_alignment_ratio": 0.12,
            "cash_flow_predictability_score": 85,
            "ebitda_to_fcf_conversion": 0.82,
            "operating_margin_ebitda": 0.68,
            "free_cash_flow_yield_pct": 10.0,
            "board_independence": 0.62,
            "disclosure_quality_score": 80,
            "audit_quality_score": 75,
            "stakeholder_rights_protection": 72,
            "dividend_yield_pct": 11.0,
            "mandatory_payout_ratio": 0.95,
            "distribution_consistency_score": 88,
            "reinvestment_rate": 0.12,
            "acquisition_track_record_score": 68,
            "debt_cost_optimization": 72,
            "net_debt_to_ebitda": 3.5,
            "weighted_avg_debt_maturity_years": 10,
            "interest_rate_hedge_ratio": 0.75,
        },
    )

    analyzer = InfraAnalyzer()
    report = analyzer.analyze(btlg11)

    print(f"{report.asset_symbol} — {btlg11.industry}")
    print("-" * 70)
    print(f"  Score Global: {report.overall_score:.1f}/100")
    print(f"  Recomendação: {report.recommendation}")
    print(f"  Nível de Risco: {report.risk_level}")
    print()
    print("  Pilares Principais:")
    for ps in report.pillar_scores:
        icon = "✓" if ps.score >= 70 else "⚠" if ps.score >= 50 else "✗"
        print(
            f"    [{icon}] {ps.pillar.value.replace('_', ' ').title()}: {ps.score:.1f}"
        )
    print()


def create_agro_examples():
    """Exemplos de análise de Fundos Agrícolas."""
    print("=" * 70)
    print("ANÁLISE DE FUNDOS AGRÍCOLAS — AGRO ANALYZER")
    print("=" * 70)
    print()

    # RZAG11.FII — Razor Agrícola (simulado)
    rzag11 = AssetData(
        symbol="RZAG11.FII",
        sector="Agrícola",
        industry="Terras Agrícolas",
        financials={
            "land_quality_score": 82,
            "crop_diversification_score": 72,
            "regional_concentration_score": 68,
            "commodity_mix_balance": 70,
            "land_appreciation_potential_score": 75,
            "water_access_quality_score": 80,
            "logistics_location_score": 65,
            "scale_advantage_score": 70,
            "yield_improvement_trend": 4.5,
            "land_expansion_pipeline_hectares": 5000,
            "tech_adoption_rate_score": 72,
            "commodity_price_cycle_position": 0.55,
            "agribusiness_experience_years": 18,
            "agronomy_team_quality_score": 78,
            "operational_efficiency_score": 75,
            "sustainability_commitment_score": 80,
            "harvest_consistency_score": 75,
            "free_cash_flow_per_hectare": 900,
            "receivables_collection_rate": 0.93,
            "cost_control_effectiveness": 70,
            "board_independence": 0.60,
            "esg_compliance_score": 78,
            "disclosure_transparency_score": 72,
            "audit_quality_score": 75,
            "dividend_yield_pct": 11.5,
            "payout_ratio": 0.92,
            "seasonality_smoothing_mechanism": True,
            "distribution_frequency_months": 3,
            "land_acquisition_track_record": 70,
            "technology_investment_ratio": 0.10,
            "crop_regional_diversification_score": 65,
            "weather_risk_hedging_score": 65,
            "crop_insurance_coverage_ratio": 0.90,
            "debt_to_assets_ratio": 0.32,
            "liquidity_reserve_months": 5,
        },
    )

    analyzer = AgroAnalyzer()
    report = analyzer.analyze(rzag11)

    print(f"{report.asset_symbol} — {rzag11.industry}")
    print("-" * 70)
    print(f"  Score Global: {report.overall_score:.1f}/100")
    print(f"  Recomendação: {report.recommendation}")
    print(f"  Nível de Risco: {report.risk_level}")
    print(f"  Yield Anual Estimado: {rzag11.financials['dividend_yield_pct']}%")
    print()
    print("  Pontos Fortes:")
    strong_pillars = [ps for ps in report.pillar_scores if ps.score >= 75]
    for ps in sorted(strong_pillars, key=lambda x: x.score, reverse=True)[:3]:
        print(f"    ✓ {ps.pillar.value.replace('_', ' ').title()}: {ps.score:.1f}")
    print()


def generate_comparison_report():
    """Gerar relatório comparativo em JSON."""
    print("=" * 70)
    print("RELATÓRIO COMPARATIVO EXPORTADO — JSON")
    print("=" * 70)
    print()

    comparison = {
        "generated_at": datetime.now().isoformat(),
        "framework_version": "11.0",
        "assets": [],
    }

    # Adicionar análises de exemplo
    equity_analyzer = EquityAnalyzer()
    fi_analyzer = FIIAnalyzer()

    petr4_report = equity_analyzer.analyze(
        AssetData(
            symbol="PETR4.SA",
            sector="Petróleo",
            industry="Refino",
            financials={
                "ebit": 52e9,
                "net_income": 41e9,
                "revenue": 470e9,
                "equity": 410e9,
                "invested_capital": 520e9,
                "dividend_yield": 9.5,
            },
        )
    )

    hlgg11_report = fi_analyzer.analyze(
        AssetData(
            symbol="HGLG11.SA",
            sector="Imobiliário",
            industry="Logística",
            financials={
                "occupancy_rate": 0.97,
                "dividend_yield": 10.5,
                "avg_lease_term_years": 9,
            },
        )
    )

    comparison["assets"].extend([petr4_report.to_dict(), hlgg11_report.to_dict()])

    print(json.dumps(comparison, indent=2, ensure_ascii=False))
    print()
    print("✓ Relatório exportado (formato JSON)")


if __name__ == "__main__":
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  IIP ATLAS MONITOR — EXEMPLOS PRÁTICOS v2.0".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    create_equity_examples()
    print()
    create_fii_examples()
    print()
    create_infra_examples()
    print()
    create_agro_examples()
    print()
    generate_comparison_report()

    print()
    print("=" * 70)
    print("EXEMPLOS COMPLETOS — TODOS OS ANALYZERS DEMONSTRADOS")
    print("=" * 70)
    print()
