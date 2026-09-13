"""Script de execução End-to-End do IIP Engine com sincronização B3, Obsidian e relatórios."""

import logging
import os
from pathlib import Path

from iip.data.b3_gateway import B3Gateway
from iip.notifications.email_sender import send_html_report_email
from iip.obsidian.dashboard import generate_portfolio_dashboard
from iip.operational.portfolio_runner import run_portfolio_cycle
from iip.reports.pdf_exporter import generate_html_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

VAULT_DIR = Path("./MeuVaultFinanceiro")
REPORTS_DIR = Path("./reports")

print("\n[IIP ENGINE] Conectando ao B3Gateway para importar custodia real...")
b3 = B3Gateway()
b3_positions = b3.fetch_user_positions("12345678900")

# Converte posições da B3 em manifesto operacional com métricas dinâmicas
manifesto = [
    {
        "ticker": pos.ticker,
        "asset_class": pos.asset_class,
        "fetched_data": {
            "quantity": pos.quantity,
            "average_price": pos.average_price,
            "total_value_brl": pos.total_value_brl,
            "institution": pos.institution,
        },
        "report_text": f"Ativo em custodia na {pos.institution}. Quantidade: {pos.quantity:.0f} cotas/acoes.",
        "metrics": {
            "QUANTITY": pos.quantity,
            "AVERAGE_PRICE": pos.average_price,
            "TOTAL_VALUE_BRL": pos.total_value_brl,
            "SCORE": 8.0,
            "VERDICT": "MANTER",
        },
    }
    for pos in b3_positions
]

# Inclui ativo internacional em carteira externa (exemplo STOCKS)
manifesto.append(
    {
        "ticker": "AAPL",
        "asset_class": "STOCKS",
        "fetched_data": {"net_income": 90000000},
        "report_text": "Apple is facing supply chain constraints but services revenue grew 15% YoY.",
        "metrics": {"PE_RATIO": 25.4, "SCORE": 7.0, "VERDICT": "REDUZIR"},
    }
)

print(f"\n[IIP ENGINE] Iniciando execucao do ciclo operacional ({len(manifesto)} ativos)...")
print(f"[IIP ENGINE] Destino do Obsidian Vault: {VAULT_DIR.absolute()}\n")

resultados = run_portfolio_cycle(assets_manifest=manifesto, vault_path=VAULT_DIR)
dashboard = generate_portfolio_dashboard(vault_path=VAULT_DIR)

# Exportação do relatório HTML consolidado
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

# Disparo opcional de notificação por e-mail se configurado
recipient = os.getenv("IIP_NOTIFICATION_EMAIL")
if recipient:
    smtp_config = {
        "host": os.getenv("IIP_SMTP_HOST", "localhost"),
        "port": int(os.getenv("IIP_SMTP_PORT", 25)),
        "username": os.getenv("IIP_SMTP_USER"),
        "password": os.getenv("IIP_SMTP_PASS"),
        "sender_email": os.getenv("IIP_SMTP_SENDER", "noreply@iipengine.com"),
    }
    send_html_report_email(report_path, smtp_config, recipient)

print("\n[IIP ENGINE] Execucao concluida com sucesso!")
print(f"Ativos Processados: {resultados['processed']}")
print(f"Erros: {resultados['errors']}")
print(f"Relatorio HTML exportado em: {report_path.absolute()}")