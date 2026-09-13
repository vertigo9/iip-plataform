"""Script de execução End-to-End do IIP Engine com exportação para o Obsidian."""

import logging
from pathlib import Path

from iip.operational.portfolio_runner import run_portfolio_cycle
from iip.obsidian.dashboard import generate_portfolio_dashboard

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

VAULT_DIR = Path("./MeuVaultFinanceiro")

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

print(f"\n🚀 Iniciando IIP Engine...")
print(f"📁 Destino do Obsidian Vault: {VAULT_DIR.absolute()}\n")

resultados = run_portfolio_cycle(assets_manifest=manifesto, vault_path=VAULT_DIR)
dashboard = generate_portfolio_dashboard(vault_path=VAULT_DIR)

print("\n✅ Execução Concluída!")
print(f"Ativos Processados: {resultados['processed']}")
print(f"Erros: {resultados['errors']}")
print(f"Abra o seu Obsidian na pasta '{VAULT_DIR.name}'!")