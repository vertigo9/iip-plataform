from datetime import date

import pytest

import iip.sources.tesouro_direto_harvester as harvester_module
from iip.analysis import AssetData, FIIAnalyzer
from iip.analysis.framework import Pillar
from iip.cli.fetch_template import (
    _fii_dividend_pillar_inputs,
    nav_change_12m_pct,
    nav_preservation_score,
)
from iip.sources.cvm_fii import FiiComplemento
from iip.sources.shared_caches import shared_fetch_caches
from iip.sources.tesouro_direto import NtnbRate
from iip.sources.tesouro_direto_harvester import (
    long_ntnb_rate_cached as real_long_ntnb_rate_cached,  # the conftest stubs the module attribute
)

RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)
CNPJ = "11.839.593/0001-09"


def _dividends_pillar(**financials):
    data = AssetData(
        symbol="X",
        sector="Tijolo",
        industry="Logístico",
        price=100.0,
        financials=financials,
    )
    report = FIIAnalyzer().analyze(data)
    return next(p for p in report.pillar_scores if p.pillar == Pillar.DIVIDENDS)


# --- the pillar: legacy calibration is untouched -----------------------------------


@pytest.mark.parametrize(
    ("dy", "expected"), [(0, 26.67), (4, 42.67), (8.33, 60.0), (12, 60.0), (20, 60.0)]
)
def test_without_a_risk_free_rate_the_original_formula_is_unchanged(dy, expected):
    # (min(dy*12,100) + min(yoc*12,100) + 80) / 3 with yoc = 0: saturates at 60
    assert _dividends_pillar(dividend_yield=dy).score == pytest.approx(
        expected, abs=0.01
    )


def test_a_risk_free_of_none_or_zero_falls_back_to_the_original_formula():
    assert _dividends_pillar(dividend_yield=12, risk_free_real_yield=None).score == 60.0
    assert _dividends_pillar(dividend_yield=12, risk_free_real_yield=0).score == 60.0


# --- the pillar: recalibrated against the risk-free rate ------------------------------


def test_yield_equal_to_the_risk_free_scores_fifty_and_twice_it_scores_a_hundred():
    at_par = _dividends_pillar(
        dividend_yield=7.3, risk_free_real_yield=7.3, payout_sustainability_score=100
    )
    double = _dividends_pillar(
        dividend_yield=14.6, risk_free_real_yield=7.3, payout_sustainability_score=100
    )

    assert at_par.score == pytest.approx((50 + 100) / 2)
    assert double.score == pytest.approx(100.0)


def test_the_yield_term_no_longer_saturates_where_real_fii_yields_live():
    scores = [
        _dividends_pillar(
            dividend_yield=dy, risk_free_real_yield=7.3, payout_sustainability_score=80
        ).score
        for dy in (7.6, 9.3, 10.8, 12.3, 14.0)
    ]

    assert scores == sorted(scores) and len(set(scores)) == len(
        scores
    )  # strictly increasing
    assert scores[-1] - scores[0] > 20  # a real spread, not a tie at 60


def test_yield_above_twice_the_risk_free_is_capped_not_rewarded_further():
    at_cap = _dividends_pillar(
        dividend_yield=14.6, risk_free_real_yield=7.3, payout_sustainability_score=80
    )
    extreme = _dividends_pillar(
        dividend_yield=25.0, risk_free_real_yield=7.3, payout_sustainability_score=80
    )

    assert extreme.score == at_cap.score


def test_sustainability_now_moves_the_pillar():
    steady = _dividends_pillar(
        dividend_yield=10, risk_free_real_yield=7.3, payout_sustainability_score=100
    )
    eroding = _dividends_pillar(
        dividend_yield=10, risk_free_real_yield=7.3, payout_sustainability_score=0
    )

    assert steady.score - eroding.score == pytest.approx(50.0)


def test_yield_on_cost_only_counts_when_supplied_in_the_new_calibration():
    without = _dividends_pillar(
        dividend_yield=10, risk_free_real_yield=7.3, payout_sustainability_score=80
    )
    zero = _dividends_pillar(
        dividend_yield=10,
        risk_free_real_yield=7.3,
        payout_sustainability_score=80,
        yield_on_cost=0,
    )
    given = _dividends_pillar(
        dividend_yield=10,
        risk_free_real_yield=7.3,
        payout_sustainability_score=80,
        yield_on_cost=12,
    )

    assert zero.score == without.score  # a constant 0 no longer drags the average down
    assert given.score != without.score  # but a real value is used


def test_negative_yield_scores_zero_on_that_term_never_below():
    pillar = _dividends_pillar(
        dividend_yield=-1.59, risk_free_real_yield=7.3, payout_sustainability_score=80
    )

    assert pillar.score == pytest.approx(40.0)  # (0 + 80) / 2


# --- NAV preservation ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (3.0, 100.0),
        (0.0, 100.0),
        (-1.0, 80.0),
        (-2.5, 50.0),
        (-4.7, 6.0),
        (-5.0, 0.0),
        (-6.1, 0.0),
    ],
)
def test_nav_preservation_score(change, expected):
    assert nav_preservation_score(change) == pytest.approx(expected)


def _row(month, vp, *, amort=0.0, cnpj=CNPJ, versao="1"):
    return FiiComplemento(
        cnpj_fundo_classe=cnpj,
        data_referencia=month,
        versao=versao,
        valores={
            "Valor_Patrimonial_Cotas": vp,
            "Percentual_Amortizacao_Cotas_Mes": amort,
        },
    )


def _series(now_vp, ago_vp, **kw):
    rows = [_row(f"2025-{m:02d}-01", ago_vp) for m in range(7, 13)]
    rows += [_row(f"2026-{m:02d}-01", now_vp) for m in range(1, 8)]
    return rows


def test_nav_change_compares_the_latest_month_with_the_same_month_a_year_earlier():
    change, reason = nav_change_12m_pct(_series(now_vp=97.0, ago_vp=100.0), CNPJ)

    assert change == -3.0 and reason is None


def test_nav_change_uses_the_latest_version_of_a_month():
    rows = _series(97.0, 100.0) + [_row("2026-07-01", 95.0, versao="2")]

    change, _ = nav_change_12m_pct(rows, CNPJ)

    assert change == -5.0


def test_nav_change_is_unavailable_without_the_month_a_year_earlier_and_says_why():
    rows = [_row(f"2026-{m:02d}-01", 100.0) for m in range(1, 8)]

    change, reason = nav_change_12m_pct(rows, CNPJ)

    assert change is None and "2025-07" in reason


def test_nav_change_refuses_when_shares_were_amortized_in_the_window():
    rows = _series(97.0, 100.0)
    rows.append(_row("2026-03-01", 97.0, amort=0.02))

    change, reason = nav_change_12m_pct(rows, CNPJ)

    assert change is None and "amortização" in reason


def test_nav_change_ignores_other_funds_and_handles_no_records():
    other = _series(50.0, 100.0)
    for r in other:
        object.__setattr__(r, "cnpj_fundo_classe", "99.999.999/0001-99")

    assert nav_change_12m_pct(other, CNPJ)[0] is None
    assert nav_change_12m_pct([], CNPJ) == (None, "sem registros do fundo na CVM")


# --- template inputs -----------------------------------------------------------------


def test_pillar_inputs_carry_the_rate_and_a_real_sustainability_score(monkeypatch):
    monkeypatch.setattr(harvester_module, "long_ntnb_rate_cached", lambda: RATE)

    financials, fetched, warnings = _fii_dividend_pillar_inputs(
        {"dividend_yield": 10.0, "payout_sustainability_score": 80},
        CNPJ,
        _series(now_vp=97.0, ago_vp=100.0),
        lambda: [],
    )

    assert financials["risk_free_real_yield"] == 7.3
    assert financials["nav_change_12m_pct"] == -3.0
    assert financials["payout_sustainability_score"] == 40.0
    assert fetched == [
        "risk_free_real_yield",
        "nav_change_12m_pct",
        "payout_sustainability_score",
    ]
    assert any("NTN-B longa" in w for w in warnings)
    assert any("proxy" in w and "-3.0%" in w for w in warnings)


def test_previous_year_is_loaded_when_the_current_year_lacks_twelve_months(monkeypatch):
    monkeypatch.setattr(harvester_module, "long_ntnb_rate_cached", lambda: RATE)
    current = [r for r in _series(97.0, 100.0) if r.data_referencia.startswith("2026")]
    previous = [r for r in _series(97.0, 100.0) if r.data_referencia.startswith("2025")]

    financials, _, _ = _fii_dividend_pillar_inputs({}, CNPJ, current, lambda: previous)

    assert financials["nav_change_12m_pct"] == -3.0


def test_without_a_rate_the_pillar_keeps_its_old_calibration_and_says_so(monkeypatch):
    monkeypatch.setattr(harvester_module, "long_ntnb_rate_cached", lambda: None)

    financials, fetched, warnings = _fii_dividend_pillar_inputs(
        {}, CNPJ, _series(97.0, 100.0), lambda: []
    )

    assert "risk_free_real_yield" not in financials
    assert "risk_free_real_yield" not in fetched
    assert any("calibração antiga" in w for w in warnings)


def test_a_rate_failure_and_a_missing_previous_year_are_warnings_not_crashes(
    monkeypatch,
):
    def rate_boom():
        raise OSError("sem rede")

    def previous_boom():
        raise OSError("cvm fora")

    monkeypatch.setattr(harvester_module, "long_ntnb_rate_cached", rate_boom)

    financials, fetched, warnings = _fii_dividend_pillar_inputs(
        {"payout_sustainability_score": 80}, CNPJ, [], previous_boom
    )

    assert financials["payout_sustainability_score"] == 80  # default untouched
    assert fetched == []
    assert any("sem rede" in w for w in warnings) and any(
        "cvm fora" in w for w in warnings
    )
    assert any("continua no valor-padrão" in w for w in warnings)


# --- the rate is fetched once per run ---------------------------------------------------


def _fake_harvester(monkeypatch, outcomes):
    """Replace the HTTP harvester; each call pops the next outcome (an exception
    is raised, anything else is returned)."""
    calls = []

    class Fake:
        def fetch_long_ntnb_rate(self):
            calls.append(1)
            outcome = outcomes[min(len(calls), len(outcomes)) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    monkeypatch.setattr(harvester_module, "TesouroDiretoHTTPHarvester", Fake)
    return calls


def test_the_rate_is_fetched_once_inside_a_shared_block_and_not_memoized_outside(
    monkeypatch,
):
    calls = _fake_harvester(monkeypatch, [RATE])

    with shared_fetch_caches():
        first = real_long_ntnb_rate_cached()
        second = real_long_ntnb_rate_cached()
    assert first is second is RATE and len(calls) == 1

    real_long_ntnb_rate_cached()
    real_long_ntnb_rate_cached()
    assert len(calls) == 3  # outside a block every call fetches


def test_a_failure_is_memoized_so_a_batch_does_not_retry_a_dead_network(monkeypatch):
    calls = _fake_harvester(monkeypatch, [OSError("sem rede")])

    with shared_fetch_caches():
        for _ in range(3):
            with pytest.raises(OSError, match="sem rede"):
                real_long_ntnb_rate_cached()

    assert len(calls) == 1
