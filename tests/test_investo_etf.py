"""ETFs do Investo (LFTB11): cota patrimonial, patrimônio líquido e ficha do produto.

Os trechos JSON abaixo foram capturados dos endpoints públicos reais em 19/09/2026."""

import datetime
import json
from types import SimpleNamespace

import pytest

from iip.cli.fetch_template import _enrich_etf_with_investo, fetch_etf_template_live
from iip.sources import investo_etf
from iip.sources.cvm_renda_fixa_harvester import CvmRendaFixaHTTPHarvester
from iip.sources.investo_etf import (
    InvestoEtfError,
    InvestoNavPoint,
    history_url,
    parse_brl,
    parse_history,
    parse_product,
    product_url,
    same_cnpj,
    supports,
)
from iip.sources.investo_etf_harvester import (
    FetchedInvestoEtf,
    InvestoEtfHTTPHarvester,
)

CNPJ = "56.176.507/0001-55"

HISTORY = [
    {
        "Data": "2026-09-17",
        "Cota Patrimonial (R$)": "R$ 126,66",
        "Patrimônio Líquido (R$)": "R$ 5.853.536.873,51",
        "Valor Índice (R$)": "R$ 2.768,63",
    },
    {
        "Data": "2026-09-16",
        "Cota Patrimonial (R$)": "R$ 126,55",
        "Patrimônio Líquido (R$)": "R$ 5.848.710.457,86",
        "Valor Índice (R$)": "R$ 2.767,07",
    },
    {
        "Data": "2026-09-15",
        "Cota Patrimonial (R$)": "R$ 126,46",
        "Patrimônio Líquido (R$)": "R$ 5.819.028.262,88",
        "Valor Índice (R$)": "R$ 2.765,04",
    },
]

PRODUCT = {
    "nome": "LFTB11",
    "codigo": 1092554,
    "aum": "R$ 5.853.536.873,51",
    "taxaAdm": "0,19% a.a.",
    "rebalanceamento": "Mensal",
    "codigoIsin": "BRLFTBCTF002",
    "dataInicio": "31/10/2024",
    "ativos": "17",
    "cnpj": "56.176.507/0001-55",
    "gestor": None,
}


# ---------------------------------------------------------------- leitura


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("R$ 126,66", 126.66),
        ("R$ 5.853.536.873,51", 5853536873.51),
        ("R$\xa0126,66", 126.66),
        ("126,66", 126.66),
        ("R$ 2.768,63", 2768.63),
        ("R$ 100", 100.0),
    ],
)
def test_parse_brl_reads_brazilian_currency(raw, expected):
    assert parse_brl(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "abc", "R$ 1.2.3", "R$ 12,3,4", None, 126.66, {}])
def test_parse_brl_refuses_what_is_not_a_clean_value(raw):
    assert parse_brl(raw) is None


def test_history_comes_back_oldest_first_with_all_the_fields():
    points = parse_history(HISTORY)

    assert [p.date.isoformat() for p in points] == [
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
    ]
    last = points[-1]
    assert last.nav_per_share == 126.66
    assert last.net_assets == pytest.approx(5853536873.51)
    assert last.index_value == pytest.approx(2768.63)


def test_history_drops_rows_it_cannot_trust_instead_of_zeroing_them():
    rows = [
        *HISTORY,
        {"Data": "sem data", "Cota Patrimonial (R$)": "R$ 130,00"},
        {"Data": "2026-09-14", "Cota Patrimonial (R$)": "R$ 0,00"},
        {"Data": "2026-09-13", "Cota Patrimonial (R$)": "n/d"},
        {"Data": "2026-09-12"},
        "lixo",
    ]
    assert [p.date.isoformat() for p in parse_history(rows)] == [
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
    ]


def test_history_keeps_the_last_row_of_a_repeated_date():
    dup = {**HISTORY[0], "Cota Patrimonial (R$)": "R$ 126,70"}
    points = parse_history([HISTORY[0], dup])
    assert len(points) == 1 and points[0].nav_per_share == 126.70


def test_history_that_is_not_a_list_gives_nothing():
    assert parse_history({"erro": "x"}) == ()
    assert parse_history(None) == ()


def test_a_missing_net_assets_does_not_discard_the_nav():
    point = parse_history(
        [{"Data": "2026-09-17", "Cota Patrimonial (R$)": "R$ 126,66"}]
    )[0]
    assert point.nav_per_share == 126.66 and point.net_assets is None


def test_product_sheet_is_read_and_a_broken_one_is_refused():
    product = parse_product(PRODUCT)
    assert (product.ticker, product.cnpj, product.isin) == (
        "LFTB11",
        CNPJ,
        "BRLFTBCTF002",
    )
    assert product.administration_fee == "0,19% a.a."
    assert parse_product({**PRODUCT, "cnpj": ""}) is None
    assert parse_product({"nome": "LFTB11"}) is None
    assert parse_product([PRODUCT]) is None


def test_same_cnpj_ignores_punctuation_and_refuses_empty():
    assert same_cnpj("56.176.507/0001-55", "56176507000155")
    assert not same_cnpj("56.176.507/0001-55", "11.839.593/0001-09")
    assert not same_cnpj("", "")


def test_only_the_verified_etf_is_supported_and_urls_are_built_from_it():
    assert supports("LFTB11") and supports(" lftb11 ")
    assert not supports("BOVA11") and not supports("XPML11")
    assert history_url("lftb11").endswith("/api/produtos/historico/LFTB11")
    assert product_url("lftb11").endswith("/api/produtos/LFTB11")


# ---------------------------------------------------------------- transporte


class _Response:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body


def _opener(routes, requested=None):
    def opener(request, timeout):
        if requested is not None:
            requested.append(request.full_url)
        return _Response(routes[request.full_url])

    return opener


def _routes(product=PRODUCT, history=HISTORY):
    return {product_url("LFTB11"): product, history_url("LFTB11"): history}


def test_harvester_fetches_the_sheet_and_the_history():
    fetched = InvestoEtfHTTPHarvester(_opener(_routes())).fetch(
        "LFTB11", expected_cnpj=CNPJ
    )
    assert fetched.product.cnpj == CNPJ
    assert fetched.latest.date.isoformat() == "2026-09-17"
    assert len(fetched.points) == 3


def test_harvester_never_returns_the_quota_of_another_fund():
    other = {**PRODUCT, "cnpj": "11.839.593/0001-09"}
    with pytest.raises(InvestoEtfError, match="CNPJ"):
        InvestoEtfHTTPHarvester(_opener(_routes(product=other))).fetch(
            "LFTB11", expected_cnpj=CNPJ
        )


def test_harvester_refuses_a_sheet_that_is_for_another_ticker():
    with pytest.raises(InvestoEtfError, match="é a de OUTRO11"):
        InvestoEtfHTTPHarvester(
            _opener(_routes(product={**PRODUCT, "nome": "OUTRO11"}))
        ).fetch("LFTB11")


def test_harvester_does_not_even_request_an_unverified_ticker():
    requested = []
    with pytest.raises(InvestoEtfError, match="não é um ETF verificado"):
        InvestoEtfHTTPHarvester(_opener({}, requested)).fetch("BOVA11")
    assert requested == []


@pytest.mark.parametrize(
    "routes, message",
    [
        (_routes(product={"nome": "LFTB11"}), "ficha"),
        (_routes(history=[]), "histórico"),
        (_routes(history=[{"Data": "x"}]), "histórico"),
    ],
)
def test_harvester_refuses_answers_outside_the_expected_format(routes, message):
    with pytest.raises(InvestoEtfError, match=message):
        InvestoEtfHTTPHarvester(_opener(routes)).fetch("LFTB11")


# ---------------------------------------------------------------- template


def _today():
    return datetime.date.today()  # noqa: DTZ011


def _fetched(days_old=1, nav=126.66, net_assets=5853536873.51):
    point = InvestoNavPoint(
        date=_today() - datetime.timedelta(days=days_old),
        nav_per_share=nav,
        net_assets=net_assets,
        index_value=2768.63,
    )
    return FetchedInvestoEtf("LFTB11", parse_product(PRODUCT), (point,))


def _stub_fetch(monkeypatch, result=None, error=None):
    def fetch(self, ticker, *, expected_cnpj=None):
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(InvestoEtfHTTPHarvester, "fetch", fetch)


TEMPLATE = {
    "symbol": "LFTB11",
    "price": 126.93,
    "financials": {"expense_ratio_pct": 0.5},
}


def test_enrichment_fills_nav_net_assets_and_market_cap(monkeypatch):
    _stub_fetch(monkeypatch, _fetched())

    template, fetched, warnings = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, 126.93, ()
    )

    assert template["financials"]["nav_per_share"] == 126.66
    assert template["financials"]["assets_under_management_millions"] == 5853.54
    assert template["financials"]["expense_ratio_pct"] == 0.5  # o resto fica
    # cotas = PL / NAV; valor de mercado = preço x cotas
    assert template["market_cap"] == pytest.approx(
        126.93 * 5853536873.51 / 126.66, abs=0.01
    )
    assert fetched == [
        "nav_per_share",
        "assets_under_management_millions",
        "market_cap",
    ]
    assert len(warnings) == 1 and "D-1" in warnings[0] and "126.66" in warnings[0]


def test_enrichment_leaves_what_the_cvm_path_already_filled(monkeypatch):
    _stub_fetch(monkeypatch, _fetched())
    base = {**TEMPLATE, "market_cap": 1.0}
    base["financials"] = {"assets_under_management_millions": 9.0}

    template, fetched, _ = _enrich_etf_with_investo(
        base, "LFTB11", CNPJ, 126.93, ("assets_under_management_millions", "market_cap")
    )

    assert template["financials"]["assets_under_management_millions"] == 9.0
    assert template["market_cap"] == 1.0
    assert fetched == ["nav_per_share"]


def test_enrichment_without_a_price_does_not_invent_a_market_cap(monkeypatch):
    _stub_fetch(monkeypatch, _fetched())
    template, fetched, _ = _enrich_etf_with_investo(
        {"financials": {}}, "LFTB11", CNPJ, None, ()
    )
    assert "market_cap" not in template and "market_cap" not in fetched


def test_a_stale_nav_is_not_used_and_says_so(monkeypatch):
    _stub_fetch(monkeypatch, _fetched(days_old=investo_etf.MAX_NAV_AGE_DAYS + 3))

    template, fetched, warnings = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, 126.93, ()
    )

    assert "nav_per_share" not in template["financials"] and fetched == []
    assert "não usada" in warnings[0]


def test_a_nav_at_the_age_limit_is_still_used(monkeypatch):
    _stub_fetch(monkeypatch, _fetched(days_old=investo_etf.MAX_NAV_AGE_DAYS))
    template, fetched, _ = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, None, ()
    )
    assert (
        template["financials"]["nav_per_share"] == 126.66 and "nav_per_share" in fetched
    )


def test_enrichment_never_raises_when_the_source_fails(monkeypatch):
    _stub_fetch(monkeypatch, error=InvestoEtfError("CNPJ da ficha difere"))

    template, fetched, warnings = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, 126.93, ()
    )

    assert template == TEMPLATE and fetched == []
    assert "CNPJ da ficha difere" in warnings[0]


def test_enrichment_is_a_silent_no_op_for_any_other_etf():
    assert _enrich_etf_with_investo(dict(TEMPLATE), "BOVA11", CNPJ, 1.0, ()) == (
        TEMPLATE,
        [],
        [],
    )


def test_etf_template_takes_the_pl_from_investo_and_drops_the_informe_diario_warning(
    monkeypatch,
):
    # a CVM não tem o LFTB11 (Informe Diário vazio); o PL e o NAV vêm do Investo
    monkeypatch.setattr(
        CvmRendaFixaHTTPHarvester,
        "fetch_diario",
        lambda self, target: SimpleNamespace(informes=[]),
    )
    _stub_fetch(monkeypatch, _fetched())

    template, resultado = fetch_etf_template_live("LFTB11", CNPJ, 2026, 9, None)

    assert template["financials"]["nav_per_share"] == 126.66
    assert template["financials"]["assets_under_management_millions"] == 5853.54
    assert "nav_per_share" in resultado.fetched_fields
    assert not any(
        w.startswith("assets_under_management_millions vem de um único mês")
        for w in resultado.warnings
    )
    # o que continua verdadeiro fica: a CVM realmente não tem o fundo
    assert any("Nenhum registro CVM" in w for w in resultado.warnings)
