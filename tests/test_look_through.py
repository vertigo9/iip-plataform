"""Valuation por transparência do FMP-FGTS Daycoval Eletrobras (registro AXIA3).

Os dados da CDA abaixo são os reais de 31/08/2026 (PL, ações e preços implícitos)."""

import io
import math
import zipfile
from datetime import date
from urllib.error import HTTPError

import pytest

from iip.portfolio.batch_core import FetchPlan, fetch_template_for, resolve_fetchers
from iip.portfolio.batch_value import value_portfolio
from iip.portfolio.look_through_value import look_through_inputs
from iip.portfolio.registry import PortfolioAsset
from iip.portfolio_data.look_through import (
    UNDERLYINGS,
    combine_margin,
    equity_weights,
    issuer_code,
)
from iip.portfolio_data.valuation import ValuationMethod
from iip.portfolio_data.valuation_methods import (
    LOOK_THROUGH_MIN_COVERAGE,
    evaluate_valuations,
    first_valuation,
    has_calculator,
)
from iip.sources.cvm_cda import (
    CdaEquity,
    CdaError,
    CdaPortfolio,
    build_url,
    parse_cda_zip,
    recent_months,
)
from iip.sources.cvm_cda_harvester import CvmCdaHTTPHarvester
from iip.sources.tesouro_direto import NtnbRate

FUND = "45.121.022/0001-48"
OTHER = "11.222.333/0001-44"
COMPANY = "00.001.180/0001-26"
NET_ASSETS = 129177461.25

PL_HEADER = "TP_FUNDO_CLASSE;{col};DENOM_SOCIAL;DT_COMPTC;VL_PATRIM_LIQ"
BLC4_HEADER = (
    "TP_FUNDO_CLASSE;{col};DENOM_SOCIAL;DT_COMPTC;TP_ATIVO;QT_POS_FINAL;"
    "VL_MERC_POS_FINAL;CD_ATIVO;CD_ISIN"
)


def _csv(header, rows):
    return "\n".join([header, *rows]) + "\n"


def _pl_row(
    cnpj,
    value,
    name="DAYCOVAL FUNDO MÚTUO DE PRIVATIZAÇÃO DO FGTS ELETROBRAS (FMP-FGTS)",
):
    return f"CLASSES - FIF;{cnpj};{name};2026-08-31;{value}"


def _eq_row(cnpj, ticker, qty, value, kind="Ação ordinária", isin="BRAXIAACNOR0"):
    return f"CLASSES - FIF;{cnpj};X;2026-08-31;{kind};{qty};{value};{ticker};{isin}"


REAL_BLC4 = [
    _eq_row(FUND, "AXIA3", "1952953.000000", "103740863.36"),
    _eq_row(FUND, "AXIA13", "0.000000", "0.00", "Ação preferencial", "BRAXIAA04PC4"),
    _eq_row(
        FUND,
        "AXIA7",
        "473623.000000",
        "25168326.22",
        "Ação preferencial",
        "BRAXIAACNPC9",
    ),
    _eq_row(
        OTHER, "PETR4", "1000.000000", "35000.00", "Ação preferencial", "BRPETRACNPR6"
    ),
]


def cda_zip(
    month="202608",
    *,
    pl_rows=None,
    blc4_rows=None,
    cnpj_col="CNPJ_FUNDO_CLASSE",
    with_pl_file=True,
):
    pl_rows = (
        pl_rows
        if pl_rows is not None
        else [_pl_row(FUND, NET_ASSETS), _pl_row(OTHER, 5000000)]
    )
    blc4_rows = blc4_rows if blc4_rows is not None else REAL_BLC4
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        if with_pl_file:
            text = _csv(PL_HEADER.format(col=cnpj_col), pl_rows)
            zf.writestr(f"cda_fi_PL_{month}.csv", text.encode("latin-1"))
        text = _csv(BLC4_HEADER.format(col=cnpj_col), blc4_rows)
        zf.writestr(f"cda_fi_BLC_4_{month}.csv", text.encode("latin-1"))
    return buffer.getvalue()


# ------------------------------------------------------------------ leitura da CDA


def test_the_fund_portfolio_is_read_from_the_cda_zip():
    portfolio = parse_cda_zip(cda_zip(), FUND, "202608")

    assert portfolio.net_assets == NET_ASSETS
    assert portfolio.reference_date == "2026-08-31"
    assert portfolio.name.startswith("DAYCOVAL FUNDO MÚTUO DE PRIVATIZAÇÃO")
    by_ticker = {e.ticker: e for e in portfolio.equities}
    assert set(by_ticker) == {"AXIA3", "AXIA13", "AXIA7"}  # o PETR4 é de outro fundo
    assert by_ticker["AXIA3"].quantity == 1952953
    assert by_ticker["AXIA3"].market_value == pytest.approx(103740863.36)
    assert by_ticker["AXIA7"].kind == "Ação preferencial"
    assert by_ticker["AXIA7"].isin == "BRAXIAACNPC9"


def test_the_cnpj_is_matched_by_digits_not_by_formatting():
    assert parse_cda_zip(cda_zip(), "45121022000148", "202608") is not None


def test_the_older_cnpj_column_name_is_understood_too():
    body = cda_zip(cnpj_col="CNPJ_FUNDO")
    assert parse_cda_zip(body, FUND, "202608").net_assets == NET_ASSETS


def test_a_fund_that_is_not_in_the_month_gives_none_and_never_another_funds_data():
    assert parse_cda_zip(cda_zip(), "99.999.999/0001-99", "202608") is None


def test_a_fund_without_positive_net_assets_gives_none():
    body = cda_zip(pl_rows=[_pl_row(FUND, 0)])
    assert parse_cda_zip(body, FUND, "202608") is None


def test_rows_it_cannot_trust_are_dropped_not_zeroed():
    rows = [
        *REAL_BLC4[:1],
        _eq_row(FUND, "", "10", "100.00"),
        _eq_row(FUND, "XXXX3", "abc", "100.00"),
        _eq_row(FUND, "YYYY3", "10", "-5.00"),
        _eq_row(FUND, "ZZZZ3", "10", ""),
    ]
    portfolio = parse_cda_zip(cda_zip(blc4_rows=rows), FUND, "202608")
    assert [e.ticker for e in portfolio.equities] == ["AXIA3"]


def test_a_zip_without_the_net_assets_file_is_an_error_not_an_empty_fund():
    with pytest.raises(CdaError, match="patrimônio líquido"):
        parse_cda_zip(cda_zip(with_pl_file=False), FUND, "202608")


def test_a_corrupt_archive_is_an_error():
    with pytest.raises(CdaError, match="zip"):
        parse_cda_zip(b"isto nao e um zip", FUND, "202608")


def test_recent_months_go_back_from_the_previous_month_across_a_year_boundary():
    assert recent_months(date(2026, 9, 19)) == ("202608", "202607", "202606")
    assert recent_months(date(2026, 1, 5)) == ("202512", "202511", "202510")
    assert recent_months(date(2026, 3, 1), count=1) == ("202602",)


def test_the_url_is_built_only_from_a_year_month():
    assert build_url("202608").endswith("/cda_fi_202608.zip")
    with pytest.raises(ValueError):
        build_url("2026-08")


# ------------------------------------------------------------------ transporte


class _Response:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body


def _opener(routes, requested=None):
    def opener(request, timeout):
        if requested is not None:
            requested.append(request.full_url)
        result = routes[request.full_url]
        if isinstance(result, Exception):
            raise result
        return _Response(result)

    return opener


def _http_error(code):
    return HTTPError("http://x", code, "erro", {}, None)


def test_the_harvester_falls_back_from_an_unpublished_month_to_the_previous_one():
    routes = {
        build_url("202609"): _http_error(404),
        build_url("202608"): cda_zip("202608"),
    }
    requested = []
    fetched = CvmCdaHTTPHarvester(_opener(routes, requested)).fetch(
        FUND, months=("202609", "202608")
    )
    assert fetched.portfolio.month == "202608"
    assert fetched.url == build_url("202608")
    assert requested == [build_url("202609"), build_url("202608")]


def test_the_harvester_skips_a_month_where_the_fund_is_absent():
    routes = {
        build_url("202608"): cda_zip(
            "202608", pl_rows=[_pl_row(OTHER, 1)], blc4_rows=[]
        ),
        build_url("202607"): cda_zip("202607"),
    }
    fetched = CvmCdaHTTPHarvester(_opener(routes)).fetch(
        FUND, months=("202608", "202607")
    )
    assert fetched.portfolio.month == "202607"


def test_the_harvester_says_what_it_tried_when_no_month_works():
    routes = {
        build_url("202608"): _http_error(404),
        build_url("202607"): cda_zip("202607", pl_rows=[]),
    }
    with pytest.raises(CdaError) as excinfo:
        CvmCdaHTTPHarvester(_opener(routes)).fetch(FUND, months=("202608", "202607"))
    assert "202608 (não publicado)" in str(excinfo.value)
    assert "202607 (fundo ausente)" in str(excinfo.value)


def test_a_server_error_is_not_mistaken_for_an_unpublished_month():
    routes = {build_url("202608"): _http_error(500)}
    with pytest.raises(HTTPError):
        CvmCdaHTTPHarvester(_opener(routes)).fetch(FUND, months=("202608",))


# ------------------------------------------------------------------ pesos e margem


def _portfolio(*equities, net_assets=NET_ASSETS):
    return CdaPortfolio(
        FUND, "FMP", "202608", "2026-08-31", net_assets, tuple(equities)
    )


def _equity(ticker, value, quantity=1.0):
    return CdaEquity(ticker, None, None, quantity, value)


def test_issuer_code_is_the_four_letters_of_the_ticker():
    assert issuer_code("AXIA7") == "AXIA"
    assert issuer_code(" axia13 ") == "AXIA"
    assert issuer_code("ABC1") == ""
    assert issuer_code("") == ""


def test_common_and_preferred_shares_of_the_same_company_add_up():
    portfolio = _portfolio(
        _equity("AXIA3", 103740863.36),
        _equity("AXIA7", 25168326.22),
        _equity("AXIA13", 0.0),
    )
    weights, unmapped = equity_weights(portfolio)
    assert weights["AXIA"] == pytest.approx((103740863.36 + 25168326.22) / NET_ASSETS)
    assert weights["AXIA"] == pytest.approx(0.9979, abs=1e-4)
    assert unmapped == 0.0


def test_a_stock_of_an_unmapped_company_lowers_the_coverage_instead_of_being_guessed():
    portfolio = _portfolio(
        _equity("AXIA3", 100_000_000.0), _equity("PETR4", 20_000_000.0)
    )
    weights, unmapped = equity_weights(portfolio)
    assert set(weights) == {"AXIA"}
    assert unmapped == pytest.approx(20_000_000.0 / NET_ASSETS)


def test_the_combined_margin_is_the_weighted_sum_and_covers_only_valued_companies():
    margin, coverage = combine_margin({"A": 0.6, "B": 0.3}, {"A": 0.10, "B": -0.20})
    assert margin == pytest.approx(0.6 * 0.10 + 0.3 * -0.20)
    assert coverage == pytest.approx(0.9)


def test_a_company_without_a_margin_is_out_of_the_coverage_not_a_zero():
    margin, coverage = combine_margin({"A": 0.6, "B": 0.3}, {"A": 0.10, "B": None})
    assert margin == pytest.approx(0.06)
    assert coverage == pytest.approx(0.6)


def test_no_margin_at_all_gives_none_and_zero_coverage():
    assert combine_margin({"A": 0.9}, {"A": None}) == (None, 0.0)
    assert combine_margin({}, {}) == (None, 0.0)


# ------------------------------------------------------------------ catálogo


def test_the_fmp_fgts_class_has_the_look_through_method_and_a_calculator():
    assert has_calculator("fmp_fgts")


def test_the_fair_value_moves_the_nav_by_the_weighted_margin():
    attempts = evaluate_valuations(
        ticker="AXIA3",
        asset_class="fmp_fgts",
        price=1.8956,
        inputs={
            "nav_per_share": 1.8956,
            "look_through_margin": 0.0219,
            "look_through_coverage": 0.9979,
        },
    )
    assert [a.method for a in attempts] == [ValuationMethod.LOOK_THROUGH]
    snapshot = first_valuation(attempts)
    assert snapshot.fair_value == pytest.approx(1.8956 * 1.0219, abs=1e-4)
    # o "preço" é o próprio NAV, então a margem da cota é a da carteira
    assert snapshot.margin_of_safety == pytest.approx(0.0219, abs=1e-4)


def test_a_negative_margin_gives_a_fair_value_below_the_nav():
    attempts = evaluate_valuations(
        ticker="AXIA3",
        asset_class="fmp_fgts",
        price=2.0,
        inputs={
            "nav_per_share": 2.0,
            "look_through_margin": -0.10,
            "look_through_coverage": 0.95,
        },
    )
    assert first_valuation(attempts).fair_value == pytest.approx(1.8)


@pytest.mark.parametrize(
    "inputs, expected",
    [
        (
            {"look_through_margin": 0.02, "look_through_coverage": 0.99},
            "cota patrimonial",
        ),
        (
            {
                "nav_per_share": 0.0,
                "look_through_margin": 0.02,
                "look_through_coverage": 0.99,
            },
            "cota patrimonial",
        ),
        ({"nav_per_share": 1.9}, "não pôde ser calculada"),
        (
            {
                "nav_per_share": 1.9,
                "look_through_margin": None,
                "look_through_coverage": 0.0,
            },
            "não pôde ser calculada",
        ),
        (
            {
                "nav_per_share": 1.9,
                "look_through_margin": 0.02,
                "look_through_coverage": 0.50,
            },
            "só 50%",
        ),
    ],
)
def test_each_missing_piece_gives_insufficient_data_with_its_reason(inputs, expected):
    attempts = evaluate_valuations(
        ticker="AXIA3", asset_class="fmp_fgts", price=1.9, inputs=inputs
    )
    assert attempts[0].status == "insufficient_data"
    assert expected in attempts[0].reason
    assert first_valuation(attempts) is None


def test_the_coverage_gate_is_inclusive_at_the_minimum():
    attempts = evaluate_valuations(
        ticker="AXIA3",
        asset_class="fmp_fgts",
        price=1.9,
        inputs={
            "nav_per_share": 1.9,
            "look_through_margin": 0.02,
            "look_through_coverage": LOOK_THROUGH_MIN_COVERAGE,
        },
    )
    assert attempts[0].status == "ok"


# ------------------------------------------------------------------ cola com a ação subjacente

PLAN = FetchPlan(ano=2026, mes=9, ano_dfp=2025, bolsai_api_key="BK", brapi_token="PK")
RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)
MARKET = {"ntnb_real_yield": 0.073}
REAL_PORTFOLIO = _portfolio(
    _equity("AXIA3", 103740863.36, 1952953),
    _equity("AXIA7", 25168326.22, 473623),
)
GRAHAM_AXIA = round(math.sqrt(22.5 * 3.16 * 42.52), 2)  # 54.98
MARGIN_AXIA = GRAHAM_AXIA / 53.80 - 1


def _stock_template(price=53.80, lpa=3.16, vpa=42.52, **more):
    return {"price": price, "financials": {"lpa": lpa, "vpa": vpa, **more}}


class _Recorder:
    def __init__(self, template):
        self.template = template
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.template, object()


def _look(portfolio=REAL_PORTFOLIO, template=None, market=MARKET):
    equity = _Recorder(template if template is not None else _stock_template())
    result = look_through_inputs(
        cnpj=FUND,
        fetch_cda=lambda cnpj: portfolio,
        fetch_equity=equity,
        plan=PLAN,
        market_inputs=market,
    )
    return result, equity


def test_the_underlying_stock_is_valued_by_the_same_equity_catalog():
    result, equity = _look()

    assert GRAHAM_AXIA == 54.98
    assert result.inputs["look_through_margin"] == pytest.approx(
        0.9979 * MARGIN_AXIA, abs=2e-4
    )
    assert result.inputs["look_through_coverage"] == pytest.approx(0.9979, abs=1e-4)
    # a empresa é buscada pelo CNPJ da COMPANHIA (a DFP é dela), não pelo do fundo
    assert equity.calls == [
        (("AXIA3", COMPANY, 2025, "BK", "PK"), {}),
    ]
    assert "CDA de 2026-08-31" in result.note
    assert "AXIA3 (99.8% do PL): Graham 54.98 contra o preço 53.80" in result.note


def test_the_underlying_is_fetched_once_even_with_common_and_preferred_shares():
    _, equity = _look()
    assert len(equity.calls) == 1


def test_a_stock_price_that_failed_is_left_out_of_the_coverage_with_the_reason():
    result, _ = _look(template=_stock_template(price=None))

    assert result.inputs["look_through_margin"] is None
    assert result.inputs["look_through_coverage"] == 0.0
    assert "preço indisponível" in result.note


def test_an_underlying_with_no_applicable_method_is_out_of_the_coverage():
    result, _ = _look(template=_stock_template(lpa=-1.0, vpa=42.52))

    assert result.inputs["look_through_margin"] is None
    assert "sem valor justo" in result.note and "Graham" in result.note


def test_unmapped_stocks_are_reported_and_lower_the_coverage():
    portfolio = _portfolio(
        _equity("AXIA3", 100_000_000.0), _equity("PETR4", 25_000_000.0)
    )
    result, _ = _look(portfolio=portfolio)

    assert result.inputs["look_through_coverage"] == pytest.approx(
        100_000_000.0 / NET_ASSETS
    )
    assert "ações sem empresa mapeada" in result.note


def test_a_portfolio_without_any_mapped_stock_gives_no_margin():
    result, equity = _look(portfolio=_portfolio(_equity("PETR4", 100_000_000.0)))

    assert result.inputs["look_through_margin"] is None
    assert equity.calls == []
    assert "nenhuma ação de empresa mapeada" in result.note


def test_a_failing_cda_or_stock_fetch_propagates_for_the_caller_to_isolate():
    def broken_cda(cnpj):
        raise CdaError("sem CDA")

    with pytest.raises(CdaError):
        look_through_inputs(
            cnpj=FUND,
            fetch_cda=broken_cda,
            fetch_equity=_Recorder({}),
            plan=PLAN,
            market_inputs=MARKET,
        )

    def broken_equity(*a, **k):
        raise RuntimeError("bolsai fora do ar")

    with pytest.raises(RuntimeError):
        look_through_inputs(
            cnpj=FUND,
            fetch_cda=lambda c: REAL_PORTFOLIO,
            fetch_equity=broken_equity,
            plan=PLAN,
            market_inputs=MARKET,
        )


def test_axia_is_the_only_verified_underlying():
    assert set(UNDERLYINGS) == {"AXIA"}
    assert UNDERLYINGS["AXIA"].company_cnpj == COMPANY


# ------------------------------------------------------------------ value_portfolio

AXIA_FUND = PortfolioAsset(
    "AXIA3",
    "fixed_income",
    subtype="Daycoval FMP FGTS / subjacente AXIA3",
    structure="Fundo Mútuo de Privatização (FMP-FGTS)",
    segment="Ações — Privatização (Eletrobras ON)",
    sector="Utilities",
    industry="Electric Utilities / Renewable",
    cnpj=FUND,
)


def _fund_template():
    return {"price": None, "financials": {"nav_per_share": 1.8956}}


def _value(positions=(AXIA_FUND,), *, cda=None, equity=None, fixed_income=None, **kw):
    fixed_income = fixed_income or _Recorder(_fund_template())
    equity = equity or _Recorder(_stock_template())
    result = value_portfolio(
        bolsai_api_key="BK",
        brapi_token="PK",
        positions=tuple(positions),
        fetch_fixed_income=fixed_income,
        fetch_equity=equity,
        fetch_cda=cda or (lambda cnpj: REAL_PORTFOLIO),
        fetch_rate=lambda: RATE,
        **kw,
    )
    return result, fixed_income, equity


def test_the_fmp_fgts_is_valued_by_look_through_against_its_own_nav():
    result, fixed_income, equity = _value()

    outcome = result.outcomes[0]
    assert outcome.status == "ok" and outcome.asset_class == "fmp_fgts"
    assert outcome.price == 1.8956  # o "preço" é o NAV da cota
    attempt = outcome.attempts[0]
    assert attempt.method == ValuationMethod.LOOK_THROUGH
    assert attempt.snapshot.fair_value == pytest.approx(
        1.8956 * (1 + 0.9979 * MARGIN_AXIA), abs=2e-4
    )
    assert attempt.snapshot.margin_of_safety == pytest.approx(
        0.9979 * MARGIN_AXIA, abs=2e-4
    )
    assert (
        "CDA de 2026-08-31" in outcome.detail
        and "AXIA3 (99.8% do PL)" in outcome.detail
    )
    # a cota vem da CVM, sem preço de mercado nem credencial de preço
    assert len(fixed_income.calls) == 1
    args, kwargs = fixed_income.calls[0]
    assert args[:2] == ("AXIA3", FUND) and kwargs == {}
    assert equity.calls[0][0][:2] == ("AXIA3", COMPANY)


def test_the_fmp_fgts_is_persisted_in_the_fixed_income_folder():
    persisted = []

    class Bridge:
        def __init__(self, vault):
            pass

        def sync_valuation_projection(self, snapshot, ticker, asset_class):
            persisted.append((ticker, asset_class, snapshot.method))

    result, _, _ = _value(persist=True, vault_path="v", bridge_cls=Bridge)

    assert result.outcomes[0].status == "ok"
    assert persisted == [("AXIA3", "fixed_income", ValuationMethod.LOOK_THROUGH)]


def test_a_cda_failure_is_isolated_and_does_not_stop_the_other_positions():
    other = PortfolioAsset(
        "CXSE3", "equity", cnpj="1", sector="Financeiro", industry="Seguros"
    )

    def broken_cda(cnpj):
        raise CdaError("sem CDA utilizável")

    equity = _Recorder(_stock_template(dividend_per_share=1.0))
    result, _, _ = _value((AXIA_FUND, other), cda=broken_cda, equity=equity)

    by = {o.ticker: o for o in result.outcomes}
    assert by["AXIA3"].status == "erro" and "sem CDA utilizável" in by["AXIA3"].detail
    assert by["CXSE3"].status == "ok"


def test_too_little_of_the_net_assets_in_valued_stocks_skips_with_the_reason():
    thin = _portfolio(_equity("AXIA3", 60_000_000.0))  # 46% do PL

    result, _, _ = _value(cda=lambda cnpj: thin)

    outcome = result.outcomes[0]
    assert outcome.status == "pulado"
    assert "só 46%" in outcome.detail


def test_an_underlying_without_a_fair_value_skips_the_fund_with_the_reason():
    equity = _Recorder(_stock_template(lpa=-2.0))

    result, _, _ = _value(equity=equity)

    outcome = result.outcomes[0]
    assert outcome.status == "pulado"
    assert "não pôde ser calculada" in outcome.detail
    assert "sem valor justo" in outcome.detail  # o porquê, da ação subjacente


def test_a_fund_that_is_not_an_fmp_fgts_is_not_looked_through():
    plain = PortfolioAsset(
        "TESOURO1",
        "fixed_income",
        subtype="Tesouro",
        cnpj="1",
        sector="x",
        industry="y",
    )

    def no_cda(cnpj):
        raise AssertionError("a CDA não deve ser buscada")

    result, _, _ = _value((plain,), cda=no_cda)

    assert result.outcomes[0].status == "pulado"
    assert "fixed_income" in result.outcomes[0].detail


def test_the_fmp_fgts_template_is_fetched_like_a_fixed_income_without_a_price():
    calls = []

    def fetch_fixed_income(*args, **kwargs):
        calls.append((args, kwargs))
        return {}, object()

    fetchers = resolve_fetchers(fixed_income=fetch_fixed_income)
    fetch_template_for("fmp_fgts", AXIA_FUND, fetchers, PLAN)

    assert calls == [(("AXIA3", FUND, 2026, 9), {})]  # nada de brapi_token
