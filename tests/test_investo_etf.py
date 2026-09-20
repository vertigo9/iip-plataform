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
    InvestoReturnPoint,
    InvestoReturns,
    history_url,
    net_inflows_ytd_millions,
    parse_brl,
    parse_fee_pct,
    parse_history,
    parse_percent,
    parse_product,
    parse_returns,
    product_url,
    returns_url,
    same_cnpj,
    supports,
    tracking_difference_pct,
    tracking_error_pct,
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


# capturado na importação, antes de a fixture abaixo trocar o método por um stub
_REAL_FETCH_RETURNS = InvestoEtfHTTPHarvester.fetch_returns


@pytest.fixture(autouse=True)
def _no_real_investo_returns(monkeypatch):
    def offline(self, ticker):
        raise InvestoEtfError("sem rede nos testes")

    monkeypatch.setattr(InvestoEtfHTTPHarvester, "fetch_returns", offline)


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
    "financials": {"expense_ratio_pct": 0.5, "custom_field": 7},
}


def test_enrichment_fills_nav_net_assets_and_market_cap(monkeypatch):
    _stub_fetch(monkeypatch, _fetched())

    template, fetched, warnings = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, 126.93, ()
    )

    assert template["financials"]["nav_per_share"] == 126.66
    assert template["financials"]["assets_under_management_millions"] == 5853.54
    assert template["financials"]["expense_ratio_pct"] == 0.19  # da ficha
    assert template["financials"]["custom_field"] == 7  # o resto fica
    # cotas = PL / NAV; valor de mercado = preço x cotas
    assert template["market_cap"] == pytest.approx(
        126.93 * 5853536873.51 / 126.66, abs=0.01
    )
    assert fetched == [
        "nav_per_share",
        "assets_under_management_millions",
        "market_cap",
        "expense_ratio_pct",
    ]
    assert "D-1" in warnings[0] and "126.66" in warnings[0]


def test_enrichment_leaves_what_the_cvm_path_already_filled(monkeypatch):
    _stub_fetch(monkeypatch, _fetched())
    base = {**TEMPLATE, "market_cap": 1.0}
    base["financials"] = {"assets_under_management_millions": 9.0}

    template, fetched, _ = _enrich_etf_with_investo(
        base, "LFTB11", CNPJ, 126.93, ("assets_under_management_millions", "market_cap")
    )

    assert template["financials"]["assets_under_management_millions"] == 9.0
    assert template["market_cap"] == 1.0
    assert fetched == ["nav_per_share", "expense_ratio_pct"]


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


# ---------------------------------------------------------------- rentabilidade


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("14,03%", 14.03),
        ("-0,23%", -0.23),
        ("0,05%", 0.05),
        ("  9,76 % ", 9.76),
        ("2%", 2.0),
    ],
)
def test_parse_percent(raw, expected):
    assert parse_percent(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["14,03", "abc", "", None, 14.03, "1,2,3%"])
def test_parse_percent_refuses_what_is_not_a_percentage(raw):
    assert parse_percent(raw) is None


@pytest.mark.parametrize(
    "raw, expected",
    [("0,19% a.a.", 0.19), ("1% ao ano", 1.0), ("Taxa de 0,50%", 0.5)],
)
def test_parse_fee_pct(raw, expected):
    assert parse_fee_pct(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "sem taxa", None, 0.19])
def test_parse_fee_pct_refuses_text_without_a_percentage(raw):
    assert parse_fee_pct(raw) is None


RETURNS = {
    "indiceReferencia": "MarketVector Brazil Treasury 760 Day Target Duration",
    "sigla": "LFTB11",
    "benchmark": "CDI",
    "tabela": {
        "ultimoAno": {
            "indice": "13,68%",
            "etf": "14,03%",
            "cotaAjustada": "14,03%",
            "ibov": "14,52%",
            "benchmark": "14,52%",
        },
        "lancamento": {"indice": "26,89%", "etf": "26,66%", "benchmark": "27,92%"},
        "meses": {"nome": "não é percentual"},
    },
    "grafico": [
        {"data": "2026-09-16", "etf": 126.55, "indice": 126.72},
        {"data": "2026-09-17", "etf": 126.66, "indice": 126.89},
        {"data": "2024-10-31", "etf": 100, "indice": 100},
    ],
}


def test_returns_table_and_series_are_read_and_ordered():
    returns = parse_returns(RETURNS)

    assert returns.ticker == "LFTB11" and returns.benchmark_name == "CDI"
    assert returns.table["ultimoAno"]["etf"] == 14.03
    assert returns.table["ultimoAno"]["indice"] == 13.68
    assert returns.table["lancamento"]["benchmark"] == 27.92
    assert [p.date.isoformat() for p in returns.series] == [
        "2024-10-31",
        "2026-09-16",
        "2026-09-17",
    ]
    assert returns.series[-1].etf == 126.66 and returns.series[-1].index == 126.89


def test_returns_drop_series_rows_they_cannot_trust():
    payload = {
        **RETURNS,
        "grafico": [
            *RETURNS["grafico"],
            {"data": "sem data", "etf": 1, "indice": 1},
            {"data": "2026-09-14", "etf": 0, "indice": 100},
            {"data": "2026-09-13", "etf": "126,66", "indice": 100},
            {"data": "2026-09-12", "etf": 126.0},
            "lixo",
        ],
    }
    assert len(parse_returns(payload).series) == 3


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"tabela": {}, "grafico": []},
        {**RETURNS, "tabela": {}},
        {**RETURNS, "grafico": [RETURNS["grafico"][0]]},
        {"grafico": RETURNS["grafico"]},
    ],
)
def test_returns_refuse_a_response_without_a_usable_table_and_series(payload):
    assert parse_returns(payload) is None


def _series(etf_returns, index_returns=None):
    """Níveis a partir de retornos por observação (índice parado se não informado)."""
    index_returns = index_returns or [0.0] * len(etf_returns)
    etf, index = [100.0], [100.0]
    for e, i in zip(etf_returns, index_returns):
        etf.append(etf[-1] * (1 + e))
        index.append(index[-1] * (1 + i))
    day = datetime.date(2026, 1, 1)
    return tuple(
        InvestoReturnPoint(day + datetime.timedelta(days=n), e, i)
        for n, (e, i) in enumerate(zip(etf, index))
    )


def test_tracking_error_matches_a_hand_computed_value():
    # diferenças diárias +0,1% e -0,1% alternadas: desvio-padrão amostral =
    # 0,001 x raiz(4/3); anualizado por raiz(252) e em %: 1,8330%
    series = _series([0.001, -0.001, 0.001, -0.001])
    result = tracking_error_pct(series, window=1, windows=4, min_windows=2)
    assert result == pytest.approx(1.8330, abs=2e-3)


def test_tracking_error_is_zero_when_the_etf_copies_the_index_exactly():
    returns = [0.001, -0.002, 0.0005, 0.0015, -0.001]
    series = _series(returns, returns)
    assert tracking_error_pct(series, window=1, windows=5, min_windows=2) == 0.0


def test_tracking_error_uses_non_overlapping_windows_ending_at_the_latest_point():
    # 11 pontos, janelas de 5: só (10<-5) e (5<-0) entram; o retorno das janelas é o
    # composto, e com o índice parado a diferença é o próprio retorno do ETF
    series = _series([0.01] * 5 + [-0.01] * 5)
    windows = [series[10].etf / series[5].etf - 1, series[5].etf / series[0].etf - 1]
    expected = statistics_stdev(windows) * (252 / 5) ** 0.5 * 100
    assert tracking_error_pct(
        series, window=5, windows=2, min_windows=2
    ) == pytest.approx(expected, abs=1e-3)


def test_tracking_error_needs_enough_windows_and_never_guesses_from_a_short_series():
    short = _series([0.001, -0.001] * 5)  # 10 observações
    assert tracking_error_pct(short) is None  # padrão: 26 janelas semanais
    assert tracking_error_pct(short, window=5, windows=52, min_windows=3) is None
    assert (
        tracking_error_pct(_series([0.001]), window=1, windows=1, min_windows=1) is None
    )


def test_tracking_error_caps_at_the_requested_number_of_windows():
    series = _series([0.001, -0.001] * 10)
    three = tracking_error_pct(series, window=1, windows=3, min_windows=2)
    twenty = tracking_error_pct(series, window=1, windows=20, min_windows=2)
    assert three != twenty


def statistics_stdev(values):
    import statistics

    return statistics.stdev(values)


def test_tracking_difference_is_etf_minus_index_from_the_official_table():
    table = parse_returns(RETURNS).table
    assert tracking_difference_pct(table) == 0.35
    assert tracking_difference_pct(table, "lancamento") == -0.23
    assert tracking_difference_pct(table, "periodo_inexistente") is None
    assert tracking_difference_pct({"ultimoAno": {"etf": 14.03}}) is None


def _nav_point(day, nav, net_assets):
    return InvestoNavPoint(datetime.date.fromisoformat(day), nav, net_assets, None)


def test_net_inflows_is_the_change_in_shares_times_the_nav():
    points = (
        _nav_point("2026-01-02", 100.0, 1_000_000_000),  # 10 milhões de cotas
        _nav_point(
            "2026-01-05", 100.0, 1_200_000_000
        ),  # 12 milhões: +2 milhões x R$ 100
    )
    assert net_inflows_ytd_millions(points, 2026) == pytest.approx(200.0)


def test_net_inflows_ignores_a_price_move_with_the_same_number_of_shares():
    points = (
        _nav_point("2026-01-02", 100.0, 1_000_000_000),
        _nav_point("2026-01-05", 101.0, 1_010_000_000),  # mesmas 10 milhões de cotas
    )
    assert net_inflows_ytd_millions(points, 2026) == pytest.approx(0.0, abs=1e-6)


def test_net_inflows_counts_redemptions_as_negative():
    points = (
        _nav_point("2026-01-02", 100.0, 1_000_000_000),
        _nav_point("2026-01-05", 100.0, 900_000_000),
    )
    assert net_inflows_ytd_millions(points, 2026) == pytest.approx(-100.0)


def test_net_inflows_only_counts_days_of_the_requested_year():
    points = (
        _nav_point("2025-12-29", 100.0, 1_000_000_000),
        _nav_point("2025-12-30", 100.0, 5_000_000_000),  # 2025: não conta
        _nav_point(
            "2026-01-02", 100.0, 5_100_000_000
        ),  # o pulo de virada conta em 2026
    )
    assert net_inflows_ytd_millions(points, 2026) == pytest.approx(100.0)
    assert net_inflows_ytd_millions(points, 2025) == pytest.approx(4000.0)


def test_net_inflows_does_not_bridge_a_day_without_net_assets():
    points = (
        _nav_point("2026-01-02", 100.0, 1_000_000_000),
        _nav_point("2026-01-05", 100.0, None),
        _nav_point("2026-01-06", 100.0, 9_000_000_000),
    )
    assert net_inflows_ytd_millions(points, 2026) is None


def test_net_inflows_is_none_without_two_days_in_the_year():
    assert net_inflows_ytd_millions((), 2026) is None
    assert (
        net_inflows_ytd_millions((_nav_point("2026-01-02", 100.0, 1e9),), 2026) is None
    )


# ---------------------------------------------------------------- transporte da rentabilidade


def test_fetch_returns_reads_the_performance_endpoint(monkeypatch):
    monkeypatch.setattr(InvestoEtfHTTPHarvester, "fetch_returns", _REAL_FETCH_RETURNS)
    requested = []
    opener = _opener({returns_url("LFTB11"): RETURNS}, requested)

    returns = InvestoEtfHTTPHarvester(opener).fetch_returns("lftb11")

    assert returns.ticker == "LFTB11" and len(returns.series) == 3
    assert requested == [returns_url("LFTB11")]


def test_fetch_returns_refuses_the_answer_of_another_fund(monkeypatch):
    monkeypatch.setattr(InvestoEtfHTTPHarvester, "fetch_returns", _REAL_FETCH_RETURNS)
    other = {**RETURNS, "sigla": "OUTRO11"}
    with pytest.raises(InvestoEtfError, match="é a de OUTRO11"):
        InvestoEtfHTTPHarvester(_opener({returns_url("LFTB11"): other})).fetch_returns(
            "LFTB11"
        )


def test_fetch_returns_refuses_an_unverified_ticker_without_requesting(monkeypatch):
    monkeypatch.setattr(InvestoEtfHTTPHarvester, "fetch_returns", _REAL_FETCH_RETURNS)
    requested = []
    with pytest.raises(InvestoEtfError, match="não é um ETF verificado"):
        InvestoEtfHTTPHarvester(_opener({}, requested)).fetch_returns("BOVA11")
    assert requested == []


def test_fetch_returns_refuses_a_broken_answer(monkeypatch):
    monkeypatch.setattr(InvestoEtfHTTPHarvester, "fetch_returns", _REAL_FETCH_RETURNS)
    with pytest.raises(InvestoEtfError, match="fora do formato"):
        InvestoEtfHTTPHarvester(
            _opener({returns_url("LFTB11"): {"x": 1}})
        ).fetch_returns("LFTB11")


# ---------------------------------------------------------------- template com rastreamento


def _stub_returns(monkeypatch, returns=None, error=None):
    def fetch_returns(self, ticker):
        if error is not None:
            raise error
        return returns

    monkeypatch.setattr(InvestoEtfHTTPHarvester, "fetch_returns", fetch_returns)


def _fetched_with_history(days_old=1):
    today = _today() - datetime.timedelta(days=days_old)
    # o par (primeiro, último) conta no ano do ÚLTIMO ponto, mesmo se o primeiro for do ano anterior
    first = InvestoNavPoint(
        today - datetime.timedelta(days=3), 100.0, 1_000_000_000.0, None
    )
    last = InvestoNavPoint(today, 100.0, 1_500_000_000.0, None)
    return FetchedInvestoEtf("LFTB11", parse_product(PRODUCT), (first, last))


def _returns_with(points=60, index_offset=0.0005):
    etf = [0.0004 * (1 if n % 2 else -1) for n in range(points)]
    idx = [index_offset * (1 if n % 3 else -1) for n in range(points)]
    return InvestoReturns(
        ticker="LFTB11",
        table=parse_returns(RETURNS).table,
        series=_series(etf, idx),
        benchmark_name="CDI",
    )


def test_enrichment_fills_cost_inflows_and_tracking_and_labels_each_one(monkeypatch):
    _stub_fetch(monkeypatch, _fetched_with_history())
    returns = _returns_with(points=60 * 5)
    _stub_returns(monkeypatch, returns)

    template, fetched, warnings = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, 126.93, ()
    )

    fin = template["financials"]
    assert fin["expense_ratio_pct"] == 0.19
    assert fin["net_inflows_ytd_millions"] == pytest.approx(
        500.0
    )  # +5 milhões de cotas
    assert fin["tracking_error_pct"] == tracking_error_pct(returns.series)
    assert fin["tracking_difference_pct"] == 0.35
    for field in (
        "expense_ratio_pct",
        "net_inflows_ytd_millions",
        "tracking_error_pct",
        "tracking_difference_pct",
    ):
        assert field in fetched
    text = " | ".join(warnings)
    assert "ESTIMATIVA" in text  # o fluxo é derivado
    assert "CALCULADO" in text and "semanal" in text  # o tracking error é calculado
    assert "diário" in text and "mensal" in text  # e as outras frequências aparecem
    assert "tabela oficial" in text  # a diferença é lida


def test_a_failing_performance_request_keeps_the_nav_and_only_loses_tracking(
    monkeypatch,
):
    _stub_fetch(monkeypatch, _fetched_with_history())
    _stub_returns(monkeypatch, error=InvestoEtfError("fora do ar"))

    template, fetched, warnings = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, 126.93, ()
    )

    fin = template["financials"]
    assert fin["nav_per_share"] == 100.0  # o que o valuation precisa segue intacto
    assert fin["expense_ratio_pct"] == 0.19
    assert "tracking_error_pct" not in fin and "tracking_difference_pct" not in fin
    assert "tracking_error_pct" not in fetched
    assert any("fora do ar" in w and "valor-padrão" in w for w in warnings)


def test_a_short_series_leaves_the_tracking_error_at_its_default(monkeypatch):
    _stub_fetch(monkeypatch, _fetched_with_history())
    _stub_returns(monkeypatch, _returns_with(points=12))

    template, fetched, warnings = _enrich_etf_with_investo(
        dict(TEMPLATE), "LFTB11", CNPJ, 126.93, ()
    )

    assert "tracking_error_pct" not in template["financials"]
    assert "tracking_error_pct" not in fetched
    assert any("curta demais" in w for w in warnings)
    # a diferença de rastreamento vem da tabela oficial e não depende do tamanho da série
    assert template["financials"]["tracking_difference_pct"] == 0.35
