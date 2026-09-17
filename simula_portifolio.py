import json
from types import SimpleNamespace
from iip.operational.portfolio_runner import run_portfolio_cycle

# Função auxiliar para simular o payload (FetchedData) retornado pelos harvesters
def make_mock(ticker, body_dict):
    return SimpleNamespace(
        ticker=ticker,
        status_code=200,
        final_url=f"https://api.mock.com/ativos/{ticker}",
        body=json.dumps(body_dict).encode("utf-8")
    )

# Manifesto simulando uma carteira diversificada
manifest = [
    {
        "ticker": "HGLG11",
        "asset_class": "FII",
        "fetched_data": make_mock("HGLG11", {"vp": 150.5}),
        "metrics": {"VP_COTA": 150.50, "PRECO": 160.00}
    },
    {
        "ticker": "PETR4",
        "asset_class": "EQUITY",
        "fetched_data": make_mock("PETR4", {"pl": 4.5}),
        "metrics": {"P_L": 4.50, "ROIC": 25.0, "PRECO": 35.50}
    },
    {
        "ticker": "IVVB11",
        "asset_class": "ETF",
        "fetched_data": make_mock("IVVB11", {"ter": 0.23}),
        "metrics": {"TAXA_ADMINISTRACAO": 0.23, "PRECO": 290.00}
    },
    {
        "ticker": "CRA_SAO_MARTINHO",
        "asset_class": "FIAGRO",
        "fetched_data": make_mock("CRA_SM", {"taxa": 105.0}),
        "metrics": {"TAXA_INDICATIVA": 105.0, "PU": 1020.50}
    }
]

print("=== INICIANDO CICLO GLOBAL DE PORTFOLIO ===")
results = run_portfolio_cycle(manifest)

print(f"\nResumo: {results['processed']} ativos processados com sucesso. {results['errors']} erros.")
print("\nObservações Geradas para o Obsidian Vault:")
for obs in results["observations"]:
    print(
        f" -> Ticker: {obs.ticker.ljust(16)} | "
        f"Classe: {obs.semantic_dimension.value.ljust(12)} | "
        f"Métrica: {obs.metric_type.ljust(20)} | "
        f"Valor: {obs.value:.2f}"
    )