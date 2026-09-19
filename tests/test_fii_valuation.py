from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from iip.cli.fetch_template import _fii_valuation_inputs
from iip.portfolio.batch_value import value_portfolio
from iip.portfolio.registry import PortfolioAsset
from iip.portfolio_data.valuation import ValuationMethod
from iip.portfolio_data.valuation_methods import (
    FII_YIELD_RISK_PREMIUM,
    data_condition_violation,
    evaluate_valuations,
    first_valuation,
    ordered_methods,
)
from iip.sources.cvm_fii import build_target
from iip.sources.cvm_fii_harvester import (
    CachedCvmFiiHarvester,
    FetchedFiiReport,
    active_fii_cache,
    shared_fii_cache,
)
from iip.sources.shared_caches import shared_fetch_caches
from iip.sources.tesouro_direto import NtnbRate

RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)


def _value(structure="Tijolo", segment="Logístico", price=99.78, **inputs):
    base = {
        "nav_per_share": 106.86,
        "dividend_per_share": 11.56,
        "dividend_yield_ttm": 10.82,
        "ntnb_real_yield": 0.073,
    }
    base.update(inputs)
    return evaluate_valuations(
        ticker="BTLG11",
        asset_class="fii",
        sector=structure,
        industry=segment,
        price=price,
        inputs=base,
    )


def _by_method(attempts):
    return {a.method: a for a in attempts}


# --- NAV ---------------------------------------------------------------------------


def test_nav_fair_value_is_the_net_asset_value_per_share():
    nav = _by_method(_value())[ValuationMethod.NAV]

    assert nav.status == "ok"
    assert nav.snapshot.fair_value == 106.86
    assert nav.snapshot.margin_of_safety == pytest.approx(
        106.86 / 99.78 - 1.0
    )  # P/VP 0.93 -> +7%


def test_nav_shows_a_premium_as_a_negative_margin_of_safety():
    nav = _by_method(_value(price=120.0))[ValuationMethod.NAV]

    assert nav.snapshot.margin_of_safety < 0


@pytest.mark.parametrize("value", [None, 0.0, -5.0])
def test_nav_without_a_positive_net_asset_value_is_insufficient(value):
    nav = _by_method(_value(nav_per_share=value))[ValuationMethod.NAV]

    assert nav.status == "insufficient_data" and nav.snapshot is None


# --- Yield: applicability by structure ---------------------------------------------


def test_yield_capitalizes_income_over_the_real_ntnb_plus_the_fii_risk_premium():
    y = _by_method(_value())[ValuationMethod.YIELD]

    required = 0.073 + FII_YIELD_RISK_PREMIUM
    assert y.status == "ok"
    assert y.snapshot.fair_value == pytest.approx(11.56 / required, abs=0.01)
    assert "7.30%" in y.reason and "3.00%" in y.reason and "10.30%" in y.reason


def test_the_premium_is_a_documented_three_points_below_the_market_implied_spread():
    # measured 18/09/2026: median tijolo yield 10.98% vs real NTN-B 7.30% -> 3.7 p.p.
    assert FII_YIELD_RISK_PREMIUM == pytest.approx(0.03)
    assert FII_YIELD_RISK_PREMIUM < 0.0368


def test_a_fund_yielding_exactly_the_required_rate_is_valued_at_its_price():
    required = 0.073 + FII_YIELD_RISK_PREMIUM
    price = 100.0
    attempts = _value(
        price=price, dividend_per_share=price * required, dividend_yield_ttm=10.3
    )

    y = _by_method(attempts)[ValuationMethod.YIELD]

    assert y.snapshot.fair_value == pytest.approx(price, abs=0.01)
    assert y.snapshot.margin_of_safety == pytest.approx(0.0, abs=1e-4)


def test_the_premium_removes_the_systematic_overstatement_against_the_nav():
    # BTLG11 (real data): without the premium the Yield ceiling sat +59% above the price
    # while the NAV said +7%; with it the two are the same order of magnitude.
    y = _by_method(_value(dividend_per_share=11.5626, price=99.78))[
        ValuationMethod.YIELD
    ]
    nav = _by_method(_value(dividend_per_share=11.5626, price=99.78))[
        ValuationMethod.NAV
    ]

    assert y.snapshot.margin_of_safety < 0.20
    assert abs(y.snapshot.margin_of_safety - nav.snapshot.margin_of_safety) < 0.15


@pytest.mark.parametrize(
    ("structure", "segment", "expected_fragment"),
    [
        ("Papel", "Crédito Imobiliário", "CDI"),
        ("Multiestratégia", "Multiestratégia", "mistura"),
    ],
)
def test_yield_is_not_applicable_to_paper_or_multi_strategy_funds(
    structure, segment, expected_fragment
):
    y = _by_method(_value(structure=structure, segment=segment))[ValuationMethod.YIELD]

    assert y.status == "not_applicable" and y.snapshot is None
    assert expected_fragment in y.reason
    # ...but the NAV anchor still values them
    assert (
        _by_method(_value(structure=structure, segment=segment))[
            ValuationMethod.NAV
        ].status
        == "ok"
    )


# --- Yield: data conditions --------------------------------------------------------


def test_yield_refuses_an_extraordinary_trailing_yield():
    reason = data_condition_violation(
        ValuationMethod.YIELD, {"dividend_yield_ttm": 20.18}
    )

    assert reason is not None and "20.2%" in reason and "extraordinária" in reason
    assert (
        data_condition_violation(ValuationMethod.YIELD, {"dividend_yield_ttm": 20.0})
        is None
    )
    assert (
        data_condition_violation(ValuationMethod.YIELD, {"dividend_yield_ttm": 12.3})
        is None
    )
    assert (
        data_condition_violation(ValuationMethod.YIELD, {}) is None
    )  # unknown is not a violation


def test_a_blocked_yield_never_computes_but_nav_still_does():
    attempts = _value(dividend_yield_ttm=20.18)

    assert _by_method(attempts)[ValuationMethod.YIELD].status == "not_applicable"
    assert first_valuation(attempts).method is ValuationMethod.NAV


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"ntnb_real_yield": None}, "NTN-B"),
        ({"dividend_per_share": None}, "12 meses"),
        ({"dividend_per_share": 0.0}, "sem distribuição"),
    ],
)
def test_yield_without_rate_or_income_is_insufficient_never_a_fallback(
    overrides, fragment
):
    y = _by_method(_value(**overrides))[ValuationMethod.YIELD]

    assert y.status == "insufficient_data" and y.snapshot is None
    assert fragment in y.reason


def test_fii_lead_method_is_always_nav():
    assert ordered_methods("fii", "Tijolo", "Logístico")[0] is ValuationMethod.NAV
    assert (
        ordered_methods("fii", "Papel", "Crédito Imobiliário")[0] is ValuationMethod.NAV
    )
    assert first_valuation(_value()).method is ValuationMethod.NAV


# --- template inputs (bolsai FII record) -------------------------------------------


def _fii(**overrides):
    base = {
        "book_value_per_share": 97.401459,
        "dividend_yield_ttm": 12.31,
        "reference_date": "2026-07-01",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_income_per_share_is_the_yield_on_net_asset_value_times_nav():
    financials, fetched, warnings = _fii_valuation_inputs(
        {"dividend_yield": 6.8}, _fii()
    )

    # HGCR11: 12.31% of R$ 97.40 = R$ 11.99 ~ 12 x R$ 1.00 paid per month
    assert financials["dividend_per_share"] == pytest.approx(11.99, abs=0.01)
    assert financials["nav_per_share"] == pytest.approx(97.4015, abs=1e-4)
    assert financials["dividend_yield_ttm"] == 12.31
    assert fetched == ["nav_per_share", "dividend_yield_ttm", "dividend_per_share"]
    assert any("patrimônio por cota" in w and "2026-07-01" in w for w in warnings)


def test_the_analyzers_own_dividend_yield_is_left_untouched():
    financials, _, _ = _fii_valuation_inputs({"dividend_yield": 6.8}, _fii())

    assert financials["dividend_yield"] == 6.8


def test_no_bolsai_record_adds_nothing():
    original = {"dividend_yield": 6.8}

    financials, fetched, warnings = _fii_valuation_inputs(original, None)

    assert financials is original and fetched == [] and warnings == []


def test_missing_yield_or_nav_never_fabricates_income_per_share():
    no_yield, fetched1, _ = _fii_valuation_inputs({}, _fii(dividend_yield_ttm=None))
    no_nav, fetched2, _ = _fii_valuation_inputs({}, _fii(book_value_per_share=None))

    assert "dividend_per_share" not in no_yield and "nav_per_share" in no_yield
    assert "dividend_per_share" not in no_nav and "dividend_yield_ttm" in no_nav
    assert "dividend_per_share" not in fetched1 + fetched2


# --- batch -------------------------------------------------------------------------


def _fii_position(ticker, structure="Tijolo", segment="Logístico"):
    return PortfolioAsset(
        ticker,
        "fund",
        subtype="FII",
        structure=structure,
        segment=segment,
        cnpj="00.000.000/0000-00",
    )


def _batch(positions, templates):
    calls = []

    def fetch_fii(symbol, cnpj, ano, bolsai_api_key):
        calls.append((symbol, ano, bolsai_api_key))
        return templates[symbol], object()

    result = value_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        positions=tuple(positions),
        fetch_fii=fetch_fii,
        fetch_rate=lambda: RATE,
        ano=2025,
    )
    return result, calls


def _template(**financials):
    return {"price": 99.78, "financials": financials}


def test_batch_values_fiis_with_nav_and_yield_and_uses_the_current_year():
    result, calls = _batch(
        [_fii_position("BTLG11")],
        {
            "BTLG11": _template(
                nav_per_share=106.86, dividend_per_share=11.56, dividend_yield_ttm=10.82
            )
        },
    )

    outcome = result.outcomes[0]
    assert outcome.status == "ok"
    methods = {a.method: a.status for a in outcome.attempts}
    assert methods == {ValuationMethod.NAV: "ok", ValuationMethod.YIELD: "ok"}
    assert calls == [
        ("BTLG11", datetime.now(UTC).year, "k")
    ]  # --ano is the DFP fiscal year, not for FIIs


def test_batch_gives_paper_funds_the_nav_only():
    result, _ = _batch(
        [_fii_position("HGCR11", "Papel", "Crédito Imobiliário")],
        {
            "HGCR11": _template(
                nav_per_share=97.4, dividend_per_share=11.99, dividend_yield_ttm=12.31
            )
        },
    )

    statuses = {a.method: a.status for a in result.outcomes[0].attempts}
    assert statuses == {
        ValuationMethod.NAV: "ok",
        ValuationMethod.YIELD: "not_applicable",
    }


# --- shared CVM FII cache ----------------------------------------------------------


def test_fii_cache_downloads_each_year_once_and_drops_the_body():
    calls = []

    class Inner:
        def fetch(self, target):
            calls.append(target.ano)
            return FetchedFiiReport(
                target=target,
                status_code=200,
                geral=(),
                ativo_passivo=(),
                complemento=(),
                body=b"x" * 1000,
            )

    cached = CachedCvmFiiHarvester(Inner())

    first = cached.fetch(build_target(2026))
    again = cached.fetch(build_target(2026))

    assert calls == [2026] and again is first and first.body == b""


def test_fii_and_dfp_caches_are_scoped_to_the_batch():
    from iip.sources.cvm_dfp_harvester import active_dfp_cache

    assert active_fii_cache() is None and active_dfp_cache() is None
    with shared_fetch_caches():
        assert active_fii_cache() is not None and active_dfp_cache() is not None
    assert active_fii_cache() is None and active_dfp_cache() is None
    with shared_fii_cache():
        assert active_fii_cache() is not None and active_dfp_cache() is None
