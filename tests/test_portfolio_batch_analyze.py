from iip.cli.fetch_template import FetchResult
from iip.portfolio.batch_analyze import _BatchDeps, analyze_portfolio
from iip.portfolio.registry import PortfolioAsset


def fake_fetch_equity_ok(symbol, cnpj, ano, bolsai_api_key, brapi_token):
    return (
        {
            "price": 33.81,
            "market_cap": 25_000_000_000.0,
            "financials": {"dividend_yield": 7.5},
        },
        FetchResult(fetched_fields=("price",)),
    )


def fake_fetch_fii_ok(symbol, cnpj, ano, bolsai_key):
    return (
        {"financials": {"dividend_yield": 8.5, "occupancy_rate": 0.9}},
        FetchResult(fetched_fields=("dividend_yield",)),
    )


def fake_fetch_fii_fails(symbol, cnpj, ano, bolsai_key):
    raise RuntimeError("simulated CVM outage")


class FakeSyncResult:
    def __init__(self, status_value, path):
        self.status = type("S", (), {"value": status_value})()
        self.path = path


class FakeKnowledgeBridge:
    def __init__(self, vault_path):
        self.vault_path = vault_path

    def sync_analysis_projection(self, report, ticker, asset_type):
        return FakeSyncResult("CREATED", f"{self.vault_path}/{ticker}.md")


def make_deps(**overrides):
    defaults = {
        "fetch_equity": fake_fetch_equity_ok,
        "fetch_fii": fake_fetch_fii_ok,
        "knowledge_bridge_cls": FakeKnowledgeBridge,
    }
    defaults.update(overrides)
    return _BatchDeps(**defaults)


def test_analyze_portfolio_skips_positions_without_real_sector_industry():
    result = analyze_portfolio(
        bolsai_api_key=None,
        brapi_token=None,
        vault_path="/tmp/vault",
        positions=(PortfolioAsset("SEMSEG3", "equity"),),
        deps=make_deps(),
    )

    assert len(result.skipped) == 1
    assert "sector/industry" in result.skipped[0].detail


def test_analyze_portfolio_uses_registry_sector_industry_for_equity():
    result = analyze_portfolio(
        bolsai_api_key=None,
        brapi_token=None,
        vault_path="/tmp/vault",
        positions=(
            PortfolioAsset(
                "BBSE3", "equity", sector="Financeiro", industry="Previdência e Seguros"
            ),
        ),
        deps=make_deps(),
    )

    assert len(result.succeeded) == 1
    assert result.succeeded[0].ticker == "BBSE3"


def test_analyze_portfolio_falls_back_to_structure_segment_for_funds():
    result = analyze_portfolio(
        bolsai_api_key=None,
        brapi_token=None,
        vault_path="/tmp/vault",
        positions=(
            PortfolioAsset(
                "BTLG11",
                "fund",
                subtype="FII",
                structure="Tijolo",
                segment="Logístico",
                cnpj="11.839.593/0001-09",
            ),
        ),
        deps=make_deps(),
    )

    assert len(result.succeeded) == 1


def test_analyze_portfolio_prefers_explicit_sector_industry_over_structure_segment():
    # Se um fundo tiver os dois preenchidos, sector/industry (mais
    # especifico) deve vencer, nao structure/segment.
    captured = {}

    class CapturingBridge(FakeKnowledgeBridge):
        def sync_analysis_projection(self, report, ticker, asset_type):
            captured["sector"] = (
                report.notes
            )  # AnalysisReport nao expoe sector diretamente
            return super().sync_analysis_projection(report, ticker, asset_type)

    result = analyze_portfolio(
        bolsai_api_key=None,
        brapi_token=None,
        vault_path="/tmp/vault",
        positions=(
            PortfolioAsset(
                "BTLG11",
                "fund",
                subtype="FII",
                structure="Tijolo",
                segment="Logístico",
                sector="Explícito",
                industry="Também Explícito",
                cnpj="11.839.593/0001-09",
            ),
        ),
        deps=make_deps(knowledge_bridge_cls=CapturingBridge),
    )
    assert len(result.succeeded) == 1


def test_analyze_portfolio_isolates_fetch_failure_per_position():
    result = analyze_portfolio(
        bolsai_api_key=None,
        brapi_token=None,
        vault_path="/tmp/vault",
        positions=(
            PortfolioAsset(
                "FALHA11",
                "fund",
                subtype="FII",
                structure="Tijolo",
                segment="Logístico",
                cnpj="99.999.999/0001-99",
            ),
            PortfolioAsset(
                "BBSE3", "equity", sector="Financeiro", industry="Previdência e Seguros"
            ),
        ),
        deps=make_deps(fetch_fii=fake_fetch_fii_fails),
    )

    assert len(result.failed) == 1
    assert result.failed[0].ticker == "FALHA11"
    assert len(result.succeeded) == 1
    assert result.succeeded[0].ticker == "BBSE3"


def test_analyze_portfolio_skips_unfetchable_asset_class():
    result = analyze_portfolio(
        bolsai_api_key=None,
        brapi_token=None,
        vault_path="/tmp/vault",
        positions=(
            PortfolioAsset(
                "COMOD11",
                "commodity",
                sector="Qualquer",
                industry="Qualquer",
            ),
        ),
        deps=make_deps(),
    )

    assert len(result.skipped) == 1
    assert "fetch automático" in result.skipped[0].detail


def test_analyze_portfolio_never_generates_a_decision():
    # analyze_portfolio nao deve importar nem chamar nada de
    # decision_engine -- isso e' deliberadamente fora do escopo do
    # comando em lote (ver docstring do modulo).
    import iip.portfolio.batch_analyze as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "decision_engine" not in source
    assert "decide(" not in source
