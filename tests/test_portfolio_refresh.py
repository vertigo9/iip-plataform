import json

from iip.cli.fetch_template import FetchResult
from iip.portfolio.refresh import refresh_portfolio
from iip.portfolio.registry import PortfolioAsset


def make_position(ticker, asset_class="fund", cnpj="11.111.111/0001-11"):
    return PortfolioAsset(ticker=ticker, asset_class=asset_class, cnpj=cnpj)


def fake_fetch_fii_ok(symbol, cnpj, ano, bolsai_key):
    return (
        {"symbol": symbol, "financials": {"dividend_yield": 8.5}},
        FetchResult(fetched_fields=("dividend_yield",), dividend_yield_months_used=7),
    )


def fake_fetch_etf_ok(symbol, cnpj, ano, mes, brapi_token):
    return (
        {"symbol": symbol, "financials": {"assets_under_management_millions": 500}},
        FetchResult(fetched_fields=("assets_under_management_millions",)),
    )


def fake_fetch_fii_fails(symbol, cnpj, ano, bolsai_key):
    raise RuntimeError("CVM indisponível")


def test_refresh_portfolio_writes_snapshot_for_fii_position(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(make_position("BTLG11", "fund"),),
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
    )

    assert len(result.succeeded) == 1
    outcome = result.succeeded[0]
    assert outcome.ticker == "BTLG11"
    snapshot = tmp_path / result.run_date / "BTLG11.json"
    assert snapshot.exists()
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert data["financials"]["dividend_yield"] == 8.5


def test_refresh_portfolio_writes_snapshot_for_etf_position(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(make_position("LFTB11", "etf"),),
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
    )

    assert len(result.succeeded) == 1
    snapshot = tmp_path / result.run_date / "LFTB11.json"
    assert snapshot.exists()


def test_refresh_portfolio_one_failure_does_not_abort_the_run(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(make_position("BROKEN11", "fund"), make_position("BTLG11", "fund")),
        fetch_fii=lambda symbol, *a: (
            fake_fetch_fii_fails(symbol, *a)
            if symbol == "BROKEN11"
            else fake_fetch_fii_ok(symbol, *a)
        ),
        fetch_etf=fake_fetch_etf_ok,
    )

    assert len(result.failed) == 1
    assert result.failed[0].ticker == "BROKEN11"
    assert len(result.succeeded) == 1
    assert result.succeeded[0].ticker == "BTLG11"


def test_refresh_portfolio_skips_positions_without_fetchable_asset_class(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(
            make_position("BTLG11", "fund"),
            # "commodity" is not a real PORTFOLIO_ASSETS class today --
            # used here purely to exercise the skip mechanism itself,
            # since every real class (fund/etf/fixed_income/equity) is
            # now fetchable.
            PortfolioAsset(ticker="XAU11", asset_class="commodity"),
        ),
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
    )

    assert len(result.succeeded) == 1
    assert len(result.skipped) == 1
    assert result.skipped[0].ticker == "XAU11"


def fake_fetch_equity_ok(symbol, cnpj, ano, bolsai_api_key, brapi_token):
    return (
        {"symbol": symbol, "financials": {"dividend_yield": 5.0}},
        FetchResult(fetched_fields=("dividend_yield",)),
    )


def test_refresh_portfolio_defaults_to_assets_refreshable_now(tmp_path):
    # No `positions=` override -- must fall back to the real registry's
    # assets_refreshable_now(), not silently do nothing.
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
        fetch_equity=fake_fetch_equity_ok,
    )
    tickers = {o.ticker for o in result.outcomes}
    assert "BTLG11" in tickers
    assert "LFTB11" in tickers
    assert (
        "BBSE3" in tickers
    )  # equity -- CNPJ-verified in the registry, refreshable via CVM DFP


def test_refresh_portfolio_reports_fetched_fields_per_position(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(make_position("BTLG11", "fund"),),
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
    )
    assert result.succeeded[0].fetched_fields == ("dividend_yield",)


def fake_fetch_fixed_income_ok(symbol, cnpj, ano, mes):
    return (
        {
            "symbol": symbol,
            "price": None,
            "financials": {"assets_under_management_millions": 14.8},
        },
        FetchResult(fetched_fields=("assets_under_management_millions",)),
    )


def test_refresh_portfolio_routes_fixed_income_positions(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(
            PortfolioAsset(
                ticker="AXIA3", asset_class="fixed_income", cnpj="45.121.022/0001-48"
            ),
        ),
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
        fetch_fixed_income=fake_fetch_fixed_income_ok,
    )

    assert len(result.succeeded) == 1
    snapshot = tmp_path / result.run_date / "AXIA3.json"
    assert snapshot.exists()
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert data["price"] is None


def test_refresh_portfolio_routes_fi_infra_via_fixed_income_not_fii(tmp_path):
    """Bug real encontrado e corrigido em 12/09/2026: FI-Infra
    (CDII11/JURO11/CPTI11) nao esta registrado como FII na CVM --
    confirmado ao vivo que o CNPJ do CDII11 nao aparece no Informe
    Mensal FII, mas aparece no Informe Diario (mesmo dataset que
    fixed_income/etf usam). Antes desta correcao, essas posicoes
    passavam pelo fetch_fii (que nao encontrava nada) e reportavam
    "ok" mesmo sem dado real algum."""
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(
            PortfolioAsset(
                ticker="CDII11",
                asset_class="fund",
                subtype="FI-Infra",
                cnpj="48.973.783/0001-16",
            ),
        ),
        fetch_fii=fake_fetch_fii_fails,  # se cair aqui por engano, o teste falha
        fetch_etf=fake_fetch_etf_ok,
        fetch_fixed_income=fake_fetch_fixed_income_ok,
    )

    assert len(result.succeeded) == 1
    assert result.succeeded[0].ticker == "CDII11"


def fake_fetch_fiagro_ok(symbol, cnpj, ano, mes, brapi_token=None):
    return (
        {"symbol": symbol, "price": None, "financials": {"dividend_yield_pct": 8.3}},
        FetchResult(fetched_fields=("dividend_yield_pct",)),
    )


def test_refresh_portfolio_routes_fi_agro_via_fiagro(tmp_path):
    """FI-Agro (CRAA11) confirmado ao vivo: CNPJ nao aparece nem no
    dataset FII nem no Informe Diario, so no dataset dedicado FIAGRO
    -- agora roteado corretamente pra fetch_fiagro, nao mais pulado."""
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(
            PortfolioAsset(
                ticker="CRAA11",
                asset_class="fund",
                subtype="FI-Agro",
                cnpj="48.903.610/0001-21",
            ),
        ),
        fetch_fii=fake_fetch_fii_fails,
        fetch_etf=fake_fetch_etf_ok,
        fetch_fixed_income=fake_fetch_fixed_income_ok,
        fetch_fiagro=fake_fetch_fiagro_ok,
    )

    assert len(result.succeeded) == 1
    assert result.succeeded[0].ticker == "CRAA11"
    snapshot = tmp_path / result.run_date / "CRAA11.json"
    assert snapshot.exists()


def test_refresh_portfolio_routes_equity_positions(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(PortfolioAsset(ticker="BBSE3", asset_class="equity"),),
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
        fetch_equity=fake_fetch_equity_ok,
    )

    assert len(result.succeeded) == 1
    snapshot = tmp_path / result.run_date / "BBSE3.json"
    assert snapshot.exists()


def test_refresh_portfolio_creates_dated_output_directory(tmp_path):
    result = refresh_portfolio(
        tmp_path,
        bolsai_api_key=None,
        brapi_token=None,
        positions=(make_position("BTLG11", "fund"),),
        fetch_fii=fake_fetch_fii_ok,
        fetch_etf=fake_fetch_etf_ok,
    )
    assert (tmp_path / result.run_date).is_dir()
