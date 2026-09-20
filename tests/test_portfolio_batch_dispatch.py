"""Como cada lote da carteira chama cada buscador de template.

Congela os argumentos EXATOS com que ``refresh_portfolio``, ``analyze_portfolio``
e ``value_portfolio`` chamam ``fetch_fii``/``etf``/``equity``/``fiagro``/
``fixed_income``. Os três repetiam o mesmo despacho por tipo (e divergem de
propósito em alguns pontos: o valuation usa o ano corrente para FII, passa o
``brapi_token`` ao FI-Infra e o ``bolsai_api_key`` ao FIAGRO), então qualquer
consolidação desse código tem de manter estas chamadas idênticas."""

from datetime import date
from types import SimpleNamespace

import pytest

from iip.portfolio.batch_analyze import _BatchDeps, analyze_portfolio
from iip.portfolio.batch_value import value_portfolio
from iip.portfolio.refresh import refresh_portfolio
from iip.portfolio.registry import PortfolioAsset
from iip.sources.tesouro_direto import NtnbRate

# data de calendário (o lote usa o ano/mês correntes), não timestamp
Y = date.today().year  # noqa: DTZ011
M = date.today().month  # noqa: DTZ011
RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)

FII = PortfolioAsset(
    "FIIX11", "fund", structure="Tijolo", segment="Logístico", cnpj="1"
)
ETF = PortfolioAsset("ETFX11", "etf", structure="Renda Fixa", segment="Pós", cnpj="2")
EQUITY = PortfolioAsset("EQTY3", "equity", sector="Setor", industry="Ind", cnpj="3")
FIAGRO = PortfolioAsset(
    "AGRO11", "fund", subtype="FI-Agro", structure="Papel", segment="Agro", cnpj="4"
)
INFRA = PortfolioAsset(
    "INFR11", "fund", subtype="FI-Infra", structure="Papel", segment="Infra", cnpj="5"
)
FIXED = PortfolioAsset(
    "FMPX3", "fixed_income", structure="Fundo", segment="FMP", cnpj="6"
)
ALL = (FII, ETF, EQUITY, FIAGRO, INFRA, FIXED)


class Recorder:
    """Buscadores falsos: guardam (args, kwargs) de cada chamada, por tipo."""

    def __init__(self):
        self.calls = {}

    def fetcher(self, kind):
        def fetch(*args, **kwargs):
            self.calls.setdefault(kind, []).append((args, kwargs))
            template = {"price": 10.0, "market_cap": 1.0, "financials": {}}
            return template, SimpleNamespace(fetched_fields=())

        return fetch


def _fetchers(rec):
    return {
        "fii": rec.fetcher("fii"),
        "etf": rec.fetcher("etf"),
        "equity": rec.fetcher("equity"),
        "fiagro": rec.fetcher("fiagro"),
        "fixed_income": rec.fetcher("fixed_income"),
    }


def _refresh(tmp_path, rec, *, ano=None):
    f = _fetchers(rec)
    refresh_portfolio(
        tmp_path,
        bolsai_api_key="BK",
        brapi_token="PK",
        ano=ano,
        positions=ALL,
        fetch_fii=f["fii"],
        fetch_etf=f["etf"],
        fetch_equity=f["equity"],
        fetch_fiagro=f["fiagro"],
        fetch_fixed_income=f["fixed_income"],
    )


class _Analyzer:
    def analyze(self, data):
        return SimpleNamespace(data=data)


class _Bridge:
    def __init__(self, vault_path):
        self.vault_path = vault_path

    def sync_analysis_projection(self, report, ticker, analyzer_type):
        return SimpleNamespace(status=SimpleNamespace(value="ok"), path="p")


def _analyze(tmp_path, rec, *, ano=None):
    f = _fetchers(rec)
    analyze_portfolio(
        bolsai_api_key="BK",
        brapi_token="PK",
        vault_path=str(tmp_path),
        ano=ano,
        positions=ALL,
        deps=_BatchDeps(
            fetch_fii=f["fii"],
            fetch_etf=f["etf"],
            fetch_equity=f["equity"],
            fetch_fiagro=f["fiagro"],
            fetch_fixed_income=f["fixed_income"],
            analyzers={
                key: _Analyzer
                for key in ("fii", "etf", "equity", "agro", "fixed_income")
            },
            knowledge_bridge_cls=_Bridge,
        ),
    )


def _value(rec, *, ano=None):
    f = _fetchers(rec)
    value_portfolio(
        bolsai_api_key="BK",
        brapi_token="PK",
        ano=ano,
        positions=ALL,
        fetch_fii=f["fii"],
        fetch_etf=f["etf"],
        fetch_equity=f["equity"],
        fetch_fiagro=f["fiagro"],
        fetch_fixed_income=f["fixed_income"],
        fetch_rate=lambda: RATE,
    )


def _expected_refresh_and_analyze(ano_fund, ano_dfp):
    return {
        "fii": [(("FIIX11", "1", ano_fund, "BK"), {})],
        "etf": [(("ETFX11", "2", ano_fund, M, "PK"), {})],
        "equity": [(("EQTY3", "3", ano_dfp, "BK", "PK"), {})],
        "fiagro": [(("AGRO11", "4", ano_fund, M, "PK"), {})],
        "fixed_income": [
            (("INFR11", "5", ano_fund, M), {}),
            (("FMPX3", "6", ano_fund, M), {}),
        ],
    }


def test_refresh_calls_each_fetcher_with_the_current_year_and_month(tmp_path):
    rec = Recorder()
    _refresh(tmp_path, rec)
    assert rec.calls == _expected_refresh_and_analyze(Y, Y - 1)


def test_refresh_uses_an_explicit_year_for_every_class(tmp_path):
    rec = Recorder()
    _refresh(tmp_path, rec, ano=2020)
    assert rec.calls == _expected_refresh_and_analyze(2020, 2020)


def test_analyze_calls_each_fetcher_exactly_like_refresh(tmp_path):
    rec = Recorder()
    _analyze(tmp_path, rec)
    assert rec.calls == _expected_refresh_and_analyze(Y, Y - 1)


def test_analyze_uses_an_explicit_year_for_every_class(tmp_path):
    rec = Recorder()
    _analyze(tmp_path, rec, ano=2020)
    assert rec.calls == _expected_refresh_and_analyze(2020, 2020)


def _expected_value(ano_dfp):
    # o valuation difere de propósito: FII/FI-Infra/FIAGRO usam o ano corrente
    # (informe mensal), o FI-Infra ganha o brapi_token, o FIAGRO ganha o
    # bolsai_api_key; a renda fixa sem ticker não tem método e não é buscada. O ETF
    # passou a ter (NAV, cota patrimonial do Investo) e é buscado como no refresh
    return {
        "fii": [(("FIIX11", "1", Y, "BK"), {})],
        "etf": [(("ETFX11", "2", Y, M, "PK"), {})],
        "fixed_income": [(("INFR11", "5", Y, M), {"brapi_token": "PK"})],
        "fiagro": [(("AGRO11", "4", Y, M, "PK"), {"bolsai_api_key": "BK"})],
        "equity": [(("EQTY3", "3", ano_dfp, "BK", "PK"), {})],
    }


def test_value_calls_its_fetchers_with_its_own_arguments():
    rec = Recorder()
    _value(rec)
    assert rec.calls == _expected_value(Y - 1)


def test_value_explicit_year_only_moves_the_fiscal_year_of_equities():
    rec = Recorder()
    _value(rec, ano=2020)
    assert rec.calls == _expected_value(2020)


def _analyze_one(tmp_path, rec, position):
    f = _fetchers(rec)
    return analyze_portfolio(
        bolsai_api_key="BK",
        brapi_token="PK",
        vault_path=str(tmp_path),
        positions=(position,),
        deps=_BatchDeps(
            fetch_equity=f["equity"], analyzers={}, knowledge_bridge_cls=_Bridge
        ),
    ).outcomes


def _value_one(rec, position):
    f = _fetchers(rec)
    return value_portfolio(
        bolsai_api_key="BK",
        brapi_token="PK",
        positions=(position,),
        fetch_equity=f["equity"],
        fetch_rate=lambda: RATE,
    ).outcomes


@pytest.mark.parametrize("runner", ["analyze", "value"])
def test_analyze_and_value_do_not_fetch_a_position_without_sector(tmp_path, runner):
    rec = Recorder()
    position = PortfolioAsset("SEMSET3", "equity", cnpj="9")
    outcomes = (
        _analyze_one(tmp_path, rec, position)
        if runner == "analyze"
        else _value_one(rec, position)
    )
    assert rec.calls == {}
    assert outcomes[0].status == "pulado"
    assert "sector/industry" in outcomes[0].detail
