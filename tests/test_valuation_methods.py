from pathlib import Path

import pytest

from iip.analysis import EquityAnalyzer
from iip.portfolio.e2e import AssetE2ERunner
from iip.portfolio_data.valuation import ValuationMethod
from iip.portfolio_data.valuation_methods import (
    applicability,
    bazin_ceiling_price,
    data_condition_violation,
    evaluate_valuations,
    first_valuation,
    graham_fair_value,
    ordered_methods,
)


class _FetchResult:
    warnings = ()


# --- calculator --------------------------------------------------------------


def test_graham_reproduces_the_published_cxse3_figure():
    # LPA 1.51 / VPA 4.60 are the figures the reference page shows for CXSE3,
    # which lists a Graham fair value of R$ 12.50.
    assert graham_fair_value(1.51, 4.60) == 12.50


@pytest.mark.parametrize(
    ("lpa", "vpa"),
    [
        (None, 4.6),
        (1.5, None),
        (None, None),
        (0.0, 4.6),
        (-0.3, 4.6),
        (1.5, -2.0),
        (1.5, 0.0),
    ],
)
def test_graham_is_none_unless_both_inputs_are_positive(lpa, vpa):
    assert graham_fair_value(lpa, vpa) is None


# --- applicability -----------------------------------------------------------


def test_graham_applies_to_regular_equity():
    fit = applicability(
        ValuationMethod.GRAHAM, "equity", "Materiais Básicos", "Madeiras e Papel"
    )
    assert fit.applicable


def test_graham_is_excluded_for_technology_by_sector_or_industry():
    by_sector = applicability(
        ValuationMethod.GRAHAM,
        "equity",
        "Utilidade Pública / Tecnologia",
        "Processamento de Dados",
    )
    by_industry = applicability(
        ValuationMethod.GRAHAM, "equity", "Serviços", "Software e Tecnologia"
    )
    assert not by_sector.applicable
    assert not by_industry.applicable
    assert "tecnologia" in by_sector.reason.lower()


def test_method_outside_the_class_catalog_is_not_applicable():
    fii = applicability(ValuationMethod.GRAHAM, "fii")
    assert not fii.applicable
    unknown = applicability(ValuationMethod.GRAHAM, "etf")
    assert not unknown.applicable
    assert "etf" in unknown.reason


# --- evaluate_valuations -----------------------------------------------------


def _statuses(attempts):
    return {a.method: a.status for a in attempts}


def test_equity_with_lpa_vpa_gets_graham_and_reports_the_rest_honestly():
    attempts = evaluate_valuations(
        ticker="cxse3",
        asset_class="equity",
        sector="Financeiro",
        industry="Seguros",
        price=20.0,
        inputs={"lpa": 1.51, "vpa": 4.60},
    )

    assert _statuses(attempts) == {
        ValuationMethod.GRAHAM: "ok",
        ValuationMethod.BAZIN: "insufficient_data",  # no dividend / no NTN-B rate given
        ValuationMethod.DCF: "not_implemented",
        ValuationMethod.RELATIVE: "not_implemented",
    }
    snapshot = first_valuation(attempts)
    assert snapshot.ticker == "CXSE3"
    assert snapshot.method is ValuationMethod.GRAHAM
    assert snapshot.fair_value == 12.50
    assert snapshot.margin_of_safety == pytest.approx(12.5 / 20.0 - 1.0)


def test_negative_earnings_yield_insufficient_data_never_a_value():
    attempts = evaluate_valuations(
        ticker="SAUD3",
        asset_class="equity",
        sector="Saúde",
        industry="Serviços",
        price=5.0,
        inputs={"lpa": -0.4, "vpa": 3.0},
    )

    graham = attempts[0]
    assert graham.status == "insufficient_data"
    assert "positivos" in graham.reason
    assert first_valuation(attempts) is None


def test_technology_equity_is_not_applicable_even_with_valid_inputs():
    attempts = evaluate_valuations(
        ticker="CSUD3",
        asset_class="equity",
        sector="Utilidade Pública / Tecnologia",
        industry="Processamento de Dados",
        price=10.0,
        inputs={"lpa": 1.0, "vpa": 4.0},
    )

    graham = next(a for a in attempts if a.method is ValuationMethod.GRAHAM)
    assert graham.status == "not_applicable"
    assert first_valuation(attempts) is None


def test_missing_price_still_gives_fair_value_without_margin_of_safety():
    attempts = evaluate_valuations(
        ticker="X", asset_class="equity", price=None, inputs={"lpa": 2.0, "vpa": 8.0}
    )

    snapshot = first_valuation(attempts)
    assert snapshot.fair_value == 18.97  # sqrt(22.5 * 2 * 8) = sqrt(360)
    assert snapshot.margin_of_safety is None


def test_class_without_catalog_reports_not_applicable():
    attempts = evaluate_valuations(
        ticker="AXIA3",
        asset_class="fixed_income",
        price=1.0,
        inputs={"lpa": 1.0, "vpa": 1.0},
    )

    assert len(attempts) == 1
    assert attempts[0].status == "not_applicable"
    assert first_valuation(attempts) is None


def test_fii_never_gets_graham_and_lacks_data_without_nav_and_income():
    attempts = evaluate_valuations(
        ticker="BTLG11",
        asset_class="fii",
        sector="Tijolo",
        industry="Logístico",
        price=100.0,
        inputs={"lpa": 1.0, "vpa": 1.0},  # equity inputs are irrelevant here
    )

    assert _statuses(attempts) == {
        ValuationMethod.NAV: "insufficient_data",
        ValuationMethod.YIELD: "insufficient_data",
    }
    assert first_valuation(attempts) is None


# --- E2E integration ---------------------------------------------------------


def _equity_template(**financials):
    def build():
        return {
            "symbol": "KLBN4",
            "sector": "Materiais Básicos",
            "industry": "Madeiras e Papel",
            "price": 3.0,
            "financials": financials,
        }, _FetchResult()

    return build


def test_e2e_computes_graham_when_no_fair_value_is_supplied(tmp_path: Path):
    result = AssetE2ERunner(
        vault_path=str(tmp_path), analyzer_factory=EquityAnalyzer
    ).run(
        ticker="KLBN4",
        asset_class="equity",
        fetch_template=_equity_template(lpa=0.24, vpa=1.52),
    )

    statuses = {step.name: step.status for step in result.steps}
    assert statuses["valuation"] == "ok"
    assert result.valuation.method is ValuationMethod.GRAHAM
    assert result.valuation.fair_value == graham_fair_value(0.24, 1.52)
    assert list(tmp_path.rglob("*.md"))


def test_e2e_stays_blocked_and_explains_why_when_no_method_can_compute(tmp_path: Path):
    result = AssetE2ERunner(
        vault_path=str(tmp_path), analyzer_factory=EquityAnalyzer
    ).run(
        ticker="KLBN4",
        asset_class="equity",
        fetch_template=_equity_template(),  # no lpa/vpa
    )

    valuation = next(step for step in result.steps if step.name == "valuation")
    assert valuation.status == "blocked"
    assert "no valuation was fabricated" in valuation.detail
    assert "Graham=insufficient_data" in valuation.detail
    assert result.valuation is None


def test_e2e_explicit_fair_value_still_takes_precedence(tmp_path: Path):
    result = AssetE2ERunner(
        vault_path=str(tmp_path), analyzer_factory=EquityAnalyzer
    ).run(
        ticker="KLBN4",
        asset_class="equity",
        fetch_template=_equity_template(lpa=0.24, vpa=1.52),
        fair_value=99.0,
        valuation_method=ValuationMethod.DCF,
    )

    assert result.valuation.fair_value == 99.0
    assert result.valuation.method is ValuationMethod.DCF


# --- Bazin with the NTN-B real yield ------------------------------------------


def test_bazin_ceiling_is_dividend_over_the_required_yield():
    assert bazin_ceiling_price(1.26, 0.073) == 17.26  # 1.26 / 0.073
    # the same dividend against Bazin's old fixed 6% would allow a higher price:
    assert bazin_ceiling_price(1.26, 0.06) == 21.0
    assert bazin_ceiling_price(1.26, 0.073) < bazin_ceiling_price(1.26, 0.06)


@pytest.mark.parametrize(
    ("dps", "rate"),
    [(None, 0.073), (1.0, None), (0.0, 0.073), (-1.0, 0.073), (1.0, 0.0), (1.0, -0.01)],
)
def test_bazin_is_none_without_positive_dividend_and_rate(dps, rate):
    assert bazin_ceiling_price(dps, rate) is None


def _bazin_attempt(**inputs):
    attempts = evaluate_valuations(
        ticker="CXSE3",
        asset_class="equity",
        sector="Financeiro",
        industry="Seguros",
        price=20.0,
        inputs=inputs,
    )
    return next(a for a in attempts if a.method is ValuationMethod.BAZIN)


def test_bazin_uses_the_supplied_ntnb_rate_and_reports_it():
    attempt = _bazin_attempt(dividend_per_share=1.26, ntnb_real_yield=0.073)

    assert attempt.status == "ok"
    assert attempt.snapshot.fair_value == 17.26
    assert attempt.snapshot.margin_of_safety == pytest.approx(17.26 / 20.0 - 1.0)
    assert "7.30%" in attempt.reason


def test_bazin_without_a_rate_never_falls_back_to_six_percent():
    attempt = _bazin_attempt(dividend_per_share=1.26)

    assert attempt.status == "insufficient_data"
    assert attempt.snapshot is None
    assert "NTN-B" in attempt.reason


def test_bazin_with_zero_dividends_is_insufficient_not_a_zero_ceiling():
    attempt = _bazin_attempt(dividend_per_share=0.0, ntnb_real_yield=0.073)

    assert attempt.status == "insufficient_data"
    assert "sem dividendos" in attempt.reason


def test_e2e_market_inputs_reach_the_bazin_calculator(tmp_path: Path):
    def build():
        return {
            "symbol": "KLBN4",
            "sector": "Materiais Básicos",
            "industry": "Madeiras e Papel",
            "price": 3.0,
            "financials": {"dividend_per_share": 0.15},
        }, _FetchResult()

    runner = AssetE2ERunner(vault_path=str(tmp_path), analyzer_factory=EquityAnalyzer)
    blocked = runner.run(ticker="KLBN4", asset_class="equity", fetch_template=build)
    ok = runner.run(
        ticker="KLBN4",
        asset_class="equity",
        fetch_template=build,
        market_inputs={"ntnb_real_yield": 0.075},
    )

    assert next(s for s in blocked.steps if s.name == "valuation").status == "blocked"
    assert next(s for s in ok.steps if s.name == "valuation").status == "ok"
    assert ok.valuation.method is ValuationMethod.BAZIN
    assert ok.valuation.fair_value == 2.0  # 0.15 / 0.075


# --- sector order and data conditions ---------------------------------------------


@pytest.mark.parametrize(
    ("sector", "industry"),
    [
        ("Utilidade Pública", "Energia Elétrica"),
        ("Utilidade Pública", "Gás"),
        ("Financeiro", "Previdência e Seguros"),
        ("Financeiro", "Intermediários Financeiros (Bancos)"),
    ],
)
def test_bazin_leads_in_dividend_centric_sectors(sector, industry):
    order = ordered_methods("equity", sector, industry)

    assert order[0] is ValuationMethod.BAZIN
    assert order[1] is ValuationMethod.GRAHAM
    assert set(order) == {
        ValuationMethod.BAZIN,
        ValuationMethod.GRAHAM,
        ValuationMethod.DCF,
        ValuationMethod.RELATIVE,
    }


@pytest.mark.parametrize(
    ("sector", "industry"),
    [
        ("Materiais Básicos", "Madeiras e Papel"),
        (
            "Financeiro",
            "Exploração de Imóveis",
        ),  # sector "Financeiro" alone is not dividend-led
        ("Saúde", "Serviços Médico-Hospitalares"),
        ("Bens Industriais", "Material de Transporte"),
    ],
)
def test_graham_leads_elsewhere(sector, industry):
    assert ordered_methods("equity", sector, industry)[0] is ValuationMethod.GRAHAM


def test_order_does_not_touch_classes_without_bazin():
    assert ordered_methods("fii", "Utilidade Pública", "Energia Elétrica") == (
        ValuationMethod.NAV,
        ValuationMethod.YIELD,
    )
    assert ordered_methods("fixed_income") == ()


def test_evaluation_puts_the_lead_method_first_so_it_is_the_one_persisted():
    inputs = {
        "lpa": 4.97,
        "vpa": 19.72,
        "dividend_per_share": 3.05,
        "ntnb_real_yield": 0.073,
        "dividend_consistency_years": 5,
        "payout_ratio": 61.0,
    }
    utility = evaluate_valuations(
        ticker="CPFE3",
        asset_class="equity",
        sector="Utilidade Pública",
        industry="Energia Elétrica",
        price=45.0,
        inputs=inputs,
    )
    industrial = evaluate_valuations(
        ticker="KLBN4",
        asset_class="equity",
        sector="Materiais Básicos",
        industry="Madeiras e Papel",
        price=45.0,
        inputs=inputs,
    )

    assert first_valuation(utility).method is ValuationMethod.BAZIN
    assert first_valuation(industrial).method is ValuationMethod.GRAHAM


@pytest.mark.parametrize("years", [0, 1, 2])
def test_bazin_needs_a_dividend_track_record(years):
    reason = data_condition_violation(
        ValuationMethod.BAZIN, {"dividend_consistency_years": years}
    )

    assert reason is not None and "mínimo 3" in reason


def test_bazin_track_record_boundary_and_unknown_fields():
    assert (
        data_condition_violation(
            ValuationMethod.BAZIN, {"dividend_consistency_years": 3}
        )
        is None
    )
    assert (
        data_condition_violation(
            ValuationMethod.BAZIN, {"dividend_consistency_years": 5}
        )
        is None
    )
    assert (
        data_condition_violation(ValuationMethod.BAZIN, {}) is None
    )  # unknown is not a violation
    assert (
        data_condition_violation(
            ValuationMethod.BAZIN, {"dividend_consistency_years": None}
        )
        is None
    )


def test_bazin_refuses_a_payout_the_earnings_cannot_sustain():
    reason = data_condition_violation(ValuationMethod.BAZIN, {"payout_ratio": 130.0})

    assert reason is not None and "130%" in reason
    assert (
        data_condition_violation(ValuationMethod.BAZIN, {"payout_ratio": 100.0}) is None
    )
    assert (
        data_condition_violation(ValuationMethod.BAZIN, {"payout_ratio": 91.8}) is None
    )


def test_graham_has_no_data_condition_beyond_its_own_positivity():
    assert (
        data_condition_violation(
            ValuationMethod.GRAHAM,
            {"dividend_consistency_years": 0, "payout_ratio": 500.0},
        )
        is None
    )


def test_a_bazin_attempt_blocked_by_its_data_says_why_and_never_computes():
    attempts = evaluate_valuations(
        ticker="ABCB4",
        asset_class="equity",
        sector="Financeiro",
        industry="Intermediários Financeiros (Bancos)",
        price=25.0,
        inputs={
            "dividend_per_share": 2.42,
            "ntnb_real_yield": 0.073,
            "dividend_consistency_years": 1,
            "lpa": 3.9,
            "vpa": 27.5,
        },
    )

    bazin = next(a for a in attempts if a.method is ValuationMethod.BAZIN)
    assert bazin.status == "not_applicable" and bazin.snapshot is None
    assert "mínimo 3" in bazin.reason
    # Graham still values it, and becomes the persisted method since Bazin has none
    assert first_valuation(attempts).method is ValuationMethod.GRAHAM


def test_fi_infra_is_valued_by_nav_only_and_the_rest_of_fixed_income_is_not():
    assert ordered_methods("fi_infra") == (ValuationMethod.NAV,)
    assert ordered_methods("fixed_income") == ()
    attempts = evaluate_valuations(
        ticker="CDII11",
        asset_class="fi_infra",
        sector="Papel",
        industry="Infraestrutura",
        price=95.2,
        inputs={"nav_per_share": 101.17},
    )
    assert attempts[0].snapshot.fair_value == 101.17


def test_etf_is_valued_by_nav_only():
    attempts = evaluate_valuations(
        ticker="LFTB11",
        asset_class="etf",
        price=126.93,
        inputs={"nav_per_share": 126.66, "lpa": 9.0, "vpa": 9.0},
    )

    assert [a.method for a in attempts] == [ValuationMethod.NAV]
    snapshot = first_valuation(attempts)
    assert snapshot.fair_value == 126.66
    # o preço acima do NAV é prêmio (margem negativa), e Graham/Bazin nem são tentados
    assert snapshot.margin_of_safety == pytest.approx(-0.002127, abs=1e-6)


def test_etf_without_a_nav_reports_insufficient_data_instead_of_a_value():
    attempts = evaluate_valuations(
        ticker="LFTB11", asset_class="etf", price=126.93, inputs={}
    )

    assert attempts[0].status == "insufficient_data"
    assert first_valuation(attempts) is None
