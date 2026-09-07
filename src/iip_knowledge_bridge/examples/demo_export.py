from pathlib import Path

from iip.analysis.agro_analyzer import AgroAnalyzer
from iip.analysis.framework import AssetData, EquityAnalyzer, FIIAnalyzer
from iip.analysis.infra_analyzer import InfraAnalyzer
from iip.export import BatchExporter, ReportExporter


def main():
    print("=" * 70)
    print("ATLAS MONITOR - EXPORT DEMONSTRATION")
    print("=" * 70)

    petr4 = AssetData(
        symbol="PETR4.SA",
        sector="Petro",
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

    hlgg11 = AssetData(
        symbol="HGLG11.SA",
        sector="Imobiliario",
        industry="Logistica",
        financials={
            "occupancy_rate": 0.97,
            "avg_lease_term_years": 9,
            "dividend_yield": 10.5,
        },
    )

    btlg11 = AssetData(
        symbol="BTLG11.SA",
        sector="Infraestrutura",
        industry="Logistica",
        financials={
            "revenue_stability_score": 82,
            "concession_remaining_years": 20,
            "cash_flow_predictability_score": 85,
            "dividend_yield_pct": 11.0,
        },
    )

    rzag11 = AssetData(
        symbol="RZAG11.FII",
        sector="Agricola",
        industry="Terras",
        financials={
            "land_quality_score": 82,
            "dividend_yield_pct": 11.5,
            "crop_insurance_coverage_ratio": 0.90,
        },
    )

    petr4_report = EquityAnalyzer().analyze(petr4)
    hlgg11_report = FIIAnalyzer().analyze(hlgg11)
    btlg11_report = InfraAnalyzer().analyze(btlg11)
    rzag11_report = AgroAnalyzer().analyze(rzag11)

    print("\n[2] Results:")
    print("  PETR4:", petr4_report.overall_score, "/100 -", petr4_report.recommendation)
    print(
        "  HGLG11:", hlgg11_report.overall_score, "/100 -", hlgg11_report.recommendation
    )
    print(
        "  BTLG11:", btlg11_report.overall_score, "/100 -", btlg11_report.recommendation
    )
    print(
        "  RZAG11:", rzag11_report.overall_score, "/100 -", rzag11_report.recommendation
    )

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    print("\n[3] Exporting...")
    ReportExporter.to_json(petr4_report, str(reports_dir / "petr4_analysis.json"))
    ReportExporter.to_html(petr4_report, str(reports_dir / "petr4_analysis.html"))
    ReportExporter.to_csv(petr4_report, str(reports_dir / "petr4_analysis.csv"))
    print("  Exported JSON, HTML, CSV")

    print("\n[4] Batch export...")
    all_reports = [petr4_report, hlgg11_report, btlg11_report, rzag11_report]
    BatchExporter.export_all(all_reports, str(reports_dir / "batch"))
    print("  Done!")

    print("\n" + "=" * 70)
    print("EXPORT COMPLETE - Check reports/ folder")
    print("=" * 70)


if __name__ == "__main__":
    main()
