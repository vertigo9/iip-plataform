"""Teste de integração do RAG no ciclo operacional da carteira."""

from iip.operational.portfolio_runner import run_portfolio_cycle


def test_run_portfolio_cycle_with_rag_enrichment():
    manifest = [
        {
            "ticker": "HGLG11",
            "asset_class": "FII",
            "report_text": "O fundo apresentou forte crescimento nos rendimentos trimestrais.",
            "metrics": {"VP_COTA": 150.0},
        }
    ]

    results = run_portfolio_cycle(manifest)
    assert results["processed"] == 1
    assert results["errors"] == 0
    # Achado real (14/09/2026): YFinanceGateway/B3Gateway sao mock fixo,
    # sem chamada de rede real -- dispatch_harvest_to_engine e' um stub
    # deliberado que NUNCA fabrica evidencia a partir desse dado. Ate'
    # esses gateways terem implementacao real, observations fica
    # sempre vazio -- isso e' o comportamento honesto esperado.
    assert results["observations"] == []
