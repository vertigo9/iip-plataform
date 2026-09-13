"""Script de execução End-to-End do IIP Engine com exportação para Obsidian e HTML/PDF."""

import logging
from pathlib import Path

from iip.operational.portfolio_runner import run_portfolio_cycle
from iip.obsidian.dashboard import generate_portfolio_dashboard
from iip.reports.pdf_exporter import generate_html_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

VAULT_DIR = Path("./MeuVaultFinanceiro")
REPORTS_DIR = Path("./reports")

manifesto = [
    {
        "ticker": "HGLG11",
        "asset_class": "FII",
        "fetched_data": {"ativo_total": 1000000},
        "report_text": "O fundo de logística assinou novos contratos com reajuste pelo IPCA, reduzindo a vacância para 2%.",
        "metrics": {"VP_COTA": 160.50, "SCORE": 8.5, "VERDICT": "COMPRAR"}
    },
    {
        "ticker": "WEGE3",
        "asset_class": "EQUITY",
        "fetched_data": {"lucro_liquido": 500000},
        "report_text": "A Weg apresentou forte crescimento na divisão de tintas e motores elétricos no exterior.",
        "metrics": {"LPA": 1.5, "SCORE": 9.0, "VERDICT": "MANTER"}
    },
    {
        "ticker": "AAPL",
        "asset_class": "STOCKS",
        "fetched_data": {"net_income": 90000000},
        "report_text": "Apple is facing supply chain constraints but services revenue grew 15% YoY.",
        "metrics": {"PE_RATIO": 25.4, "SCORE": 7.0, "VERDICT": "REDUZIR"}
    }
]

print("\n[IIP ENGINE] Iniciando execucao do ciclo operacional...")
print(f"[IIP ENGINE] Destino do Obsidian Vault: {VAULT_DIR.absolute()}\n")

resultados = run_portfolio_cycle(assets_manifest=manifesto, vault_path=VAULT_DIR)
dashboard = generate_portfolio_dashboard(vault_path=VAULT_DIR)

# Coleta o resumo dos ativos para a exportacao de relatorio HTML/PDF
assets_summary = [
    {
        "ticker": item["ticker"],
        "asset_class": item["asset_class"],
        "spot_price_brl": item["metrics"].get("SPOT_PRICE_BRL", item["metrics"].get("SPOT_PRICE", 0.0)),
        "score": item["metrics"].get("SCORE", "N/A"),
        "verdict": item["metrics"].get("VERDICT", "AGUARDAR"),
    }
    for item in manifesto
]

report_path = generate_html_report(assets_summary, REPORTS_DIR / "relatorio_consolidado.html")

print("\n[IIP ENGINE] Execucao concluida com sucesso!")
print(f"Ativos Processados: {resultados['processed']}")
print(f"Erros: {resultados['errors']}")
print(f"Relatorio HTML exportado em: {report_path.absolute()}")