from pathlib import Path

import pytest

from iip.analysis import EquityAnalyzer
from iip.portfolio.e2e import AssetE2ERunner
from iip.portfolio_data.valuation import ValuationMethod
from iip.portfolio_data.valuation_methods import (
    applicability,
    evaluate_valuations,
    first_valuation,
    graham_fair_value,
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
    [(None, 4.6), (1.5, None), (None, None), (0.0, 4.6), (-0.3, 4.6), (1.5, -2.0), (1.5, 0.0)],
)
def test_graham_is_none_unless_both_inputs_are_positive(lpa, vpa):
    assert graham_fair_value(lpa, vpa) is None


# --- applicability -----------------------------------------------------------


def test_graham_applies_to_regular_equity():
    fit = applicability(ValuationMethod.GRAHAM, "equity", "Materiais Básicos", "Madeiras e Papel")
    assert fit.applicable


def test_graham_is_excluded_for_technology_by_sector_or_industry():
    by_sector = applicability(
        ValuationMethod.GRAHAM, "equity", "Utilidade Pública / Tecnologia", "Processamento de Dados"
    )
    by_industry = applicability(ValuationMethod.GRAHAM, "equity", "Serviços", "Software e Tecnologia")
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


def test_equity_with_lpa_vpa_gets_graham_and_reports_the_rest_as_not_implemented():
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
        ValuationMethod.BAZIN: "not_implemented",
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

    assert attempts[0].method is ValuationMethod.GRAHAM
    assert attempts[0].status == "not_applicable"
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
        ticker="IVVB11", asset_class="etf", price=1.0, inputs={"lpa": 1.0, "vpa": 1.0}
    )

    assert len(attempts) == 1
    assert attempts[0].status == "not_applicable"
    assert first_valuation(attempts) is None


def test_fii_gets_no_graham_and_no_value_yet():
    attempts = evaluate_valuations(
        ticker="BTLG11", asset_class="fii", price=100.0, inputs={"lpa": 1.0, "vpa": 1.0}
    )

    assert _statuses(attempts) == {
        ValuationMethod.NAV: "not_implemented",
        ValuationMethod.YIELD: "not_implemented",
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
