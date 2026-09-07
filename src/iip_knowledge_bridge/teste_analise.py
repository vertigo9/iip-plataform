from pathlib import Path

from iip.analysis.framework import AssetData, EquityAnalyzer, FIIAnalyzer
from iip.export import ReportExporter


def analisar_acao():
    print("=" * 60)
    print("ANALISANDO AÇAO - PETR4.SA")
    print("=" * 60)

    data = AssetData(
        symbol="PETR4.SA",
        sector="Petroleo e Gas",
        industry="Refino",
        financials={
            "ebit": 52e9,
            "net_income": 41e9,
            "revenue": 470e9,
            "equity": 410e9,
            "invested_capital": 520e9,
            "revenue_growth_3y": 8.5,
            "earnings_growth_3y": 12.0,
            "dividend_yield": 9.5,
            "debt_to_equity": 0.45,
            "interest_coverage": 5.5,
        },
    )

    report = EquityAnalyzer().analyze(data)

    print(f"Asset: {report.asset_symbol}")
    print(f"Score Global: {report.overall_score:.1f}/100")
    print(f"Recomendacao: {report.recommendation}")
    print(f"Nivel de Risco: {report.risk_level}")
    print()
    print("Detalhamento por Pilar:")

    for ps in report.pillar_scores:
        print(f"  {ps.pillar.value.replace('_', ' ').title():25s} - {ps.score:.1f}/100")

    return report


def analisar_fii():
    print()
    print("=" * 60)
    print("ANALISANDO FII - HGLG11.SA")
    print("=" * 60)

    data = AssetData(
        symbol="HGLG11.SA",
        sector="Imobiliario",
        industry="Logistica",
        financials={
            "occupancy_rate": 0.97,
            "avg_lease_term_years": 9,
            "dividend_yield": 10.5,
            "npa_growth_3y": 12.0,
        },
    )

    report = FIIAnalyzer().analyze(data)

    print(f"Asset: {report.asset_symbol}")
    print(f"Score Global: {report.overall_score:.1f}/100")
    print(f"Recomendacao: {report.recommendation}")
    print(f"Nivel de Risco: {report.risk_level}")

    return report


def exportar_relatorio(report):
    print()
    print("=" * 60)
    print("EXPORTANDO RELATORIO")
    print("=" * 60)

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    filename_base = report.asset_symbol.replace(".", "_")

    ReportExporter.to_json(report, str(reports_dir / f"{filename_base}_analysis.json"))
    print(f"  [OK] JSON: reports/{filename_base}_analysis.json")

    ReportExporter.to_html(report, str(reports_dir / f"{filename_base}_analysis.html"))
    print(f"  [OK] HTML: reports/{filename_base}_analysis.html")

    ReportExporter.to_csv(report, str(reports_dir / f"{filename_base}_analysis.csv"))
    print(f"  [OK] CSV: reports/{filename_base}_analysis.csv")

    return filename_base


def main():
    print()
    print("#" * 60)
    print("#  IIP PLATFORM - TESTE DE ANÁLISE")
    print("#" * 60)
    print()

    # Analisar PETR4
    petr4_report = analisar_acao()

    # Analisar FII
    hlgg11_report = analisar_fii()

    # Exportar PETR4
    filename = exportar_relatorio(petr4_report)

    print()
    print("#" * 60)
    print("#  TESTE COMPLETO!")
    print("#" * 60)
    print()
    print(f"Abrir relatorio: explorer reports/{filename}_analysis.html")
    print()


if __name__ == "__main__":
    main()
