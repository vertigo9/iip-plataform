"""Payout ratio, dividend history/streak, and the shared DFP cache."""

import pytest

from iip.cli.fetch_template import fetch_equity_template_live
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFundamentals
from iip.sources.cvm_dfp import (
    CompanyFundamentals,
    DfpRow,
    build_target,
    consecutive_dividend_years,
    dividend_history,
    extract_fundamentals,
)
from iip.sources.cvm_dfp_harvester import (
    CachedCvmDfpHarvester,
    CvmDfpHTTPHarvester,
    FetchedDfpYear,
)
from tests.test_cvm_dfp import (  # noqa: F401 (fixture)
    NON_FINANCIAL_CNPJ,
    make_zip,
    parsed,
)
from tests.test_fetch_equity import make_bolsai_fundamentals

CNPJ_A = "11.111.111/0001-11"
CNPJ_B = "22.222.222/0001-22"
CNPJ_Z = "99.999.999/0001-99"


def _dfc(cnpj, year, valor, *, ordem="ÚLTIMO", code="6.03.08", label="Dividendos pagos"):
    return DfpRow(
        cnpj_cia=cnpj, ordem_exerc=ordem, dt_fim_exerc=f"{year}-12-31",
        cd_conta=code, ds_conta=label, vl_conta=valor, escala="MIL",
    )


# --- payout ratio ----------------------------------------------------------------


def test_payout_ratio_is_paid_dividends_over_net_income_in_percent(parsed):  # noqa: F811
    dfc = (_dfc(NON_FINANCIAL_CNPJ, 2025, -957000.0),)

    result = extract_fundamentals(2025, NON_FINANCIAL_CNPJ, dfc_con=dfc, **parsed)

    assert result.lucro_liquido_brl == 1_678_211_000.0  # DRE scale MIL -> BRL
    assert result.payout_ratio_pct == pytest.approx(957_000_000 / 1_678_211_000 * 100, abs=0.01)


def test_payout_ratio_is_not_capped_and_guards_missing_or_non_positive_income():
    base = {
        "cnpj_cia": "x", "ano_referencia": 2025, "consolidado": True, "ativo_total": 1.0,
        "patrimonio_liquido": 1.0, "receita": 1.0, "lucro_liquido": 1.0, "ebit": 1.0,
        "passivo_nao_circulante": 1.0, "dividendos_pagos": 150.0, "lucro_liquido_brl": 100.0,
    }
    assert CompanyFundamentals(**base).payout_ratio_pct == 150.0  # paid out more than earned
    assert CompanyFundamentals(**{**base, "dividendos_pagos": 0.0}).payout_ratio_pct == 0.0
    assert CompanyFundamentals(**{**base, "dividendos_pagos": None}).payout_ratio_pct is None
    assert CompanyFundamentals(**{**base, "lucro_liquido_brl": None}).payout_ratio_pct is None
    assert CompanyFundamentals(**{**base, "lucro_liquido_brl": 0.0}).payout_ratio_pct is None
    assert CompanyFundamentals(**{**base, "lucro_liquido_brl": -50.0}).payout_ratio_pct is None


# --- history and streak ----------------------------------------------------------


def test_dividend_history_reads_only_the_files_own_year_never_the_prior_column():
    # ABCB4's real 2025 file zeroes its 2024 comparative: it must not count.
    rows = (_dfc(CNPJ_A, 2025, -300.0), _dfc(CNPJ_A, 2024, 0.0, ordem="PENÚLTIMO"))

    assert dividend_history(CNPJ_A, dfc_con=rows, dfc_ind=()) == {2025: 300_000.0}


def test_dividend_history_prefers_consolidated_and_omits_years_without_a_line():
    con = (_dfc(CNPJ_A, 2025, -300.0),)
    ind = (_dfc(CNPJ_A, 2025, -999.0), _dfc(CNPJ_A, 2024, -999.0))
    other_company = (_dfc(CNPJ_B, 2024, -1.0),)

    assert dividend_history(CNPJ_A, dfc_con=con + other_company, dfc_ind=ind) == {2025: 300_000.0}
    assert dividend_history(CNPJ_A, dfc_con=(), dfc_ind=ind) == {2025: 999_000.0, 2024: 999_000.0}
    assert dividend_history(CNPJ_Z, dfc_con=con, dfc_ind=ind) == {}


def test_consecutive_dividend_years_counts_back_and_stops_at_zero_or_unknown():
    full = {2025: 1.0, 2024: 1.0, 2023: 1.0, 2022: 1.0, 2021: 1.0, 2020: 1.0}
    assert consecutive_dividend_years(full, 2025) == 5  # capped by the 5-year window
    assert consecutive_dividend_years(full, 2025, window=3) == 3
    assert consecutive_dividend_years({2025: 1.0, 2024: 1.0, 2023: 0.0, 2022: 1.0}, 2025) == 2
    assert consecutive_dividend_years({2025: 1.0, 2024: 1.0, 2022: 1.0}, 2025) == 2  # unknown != paid
    assert consecutive_dividend_years({2025: 0.0, 2024: 1.0}, 2025) == 0
    assert consecutive_dividend_years({2024: 1.0}, 2025) is None  # latest year unknown
    assert consecutive_dividend_years({}, 2025) is None


# --- shared DFP cache ------------------------------------------------------------


def test_cached_harvester_downloads_each_fiscal_year_once_and_drops_the_body():
    calls = []

    class Inner:
        def fetch(self, target):
            calls.append(target.ano)
            return FetchedDfpYear(
                target=target, status_code=200, bpa_con=(), bpa_ind=(), bpp_con=(),
                bpp_ind=(), dre_con=(), dre_ind=(), body=b"x" * 1000,
            )

    cached = CachedCvmDfpHarvester(Inner())

    first = cached.fetch(build_target(2025))
    again = cached.fetch(build_target(2025))
    cached.fetch(build_target(2022))

    assert calls == [2025, 2022]
    assert again is first
    assert first.body == b""  # raw ZIP is not kept in memory


# --- template wiring -------------------------------------------------------------


def _mock_dfp_years(monkeypatch, paid_by_year, *, fail_years=(), calls=None):
    """Each fake file for fiscal year N carries year N (ÚLTIMO) and, like the real
    ZIPs, a prior-year column (PENÚLTIMO) -- here deliberately zeroed, as
    ABCB4's real 2025 file does, to prove the template ignores it. ``paid_by_year``
    maps year -> R$ thousands paid (0 = a reported zero; a missing year has no
    dividend line)."""

    def fake_fetch(self, target):
        import iip.sources.cvm_dfp_harvester as mod

        if calls is not None:
            calls.append(target.ano)
        if target.ano in fail_years:
            raise OSError("rede caiu")
        body = make_zip()
        rows = []
        if target.ano in paid_by_year:
            rows.append(_dfc(NON_FINANCIAL_CNPJ, target.ano, -paid_by_year[target.ano]))
        rows.append(_dfc(NON_FINANCIAL_CNPJ, target.ano - 1, 0.0, ordem="PENÚLTIMO"))
        return mod.FetchedDfpYear(
            target=target, status_code=200,
            bpa_con=mod.parse_bpa_con(body), bpa_ind=mod.parse_bpa_ind(body),
            bpp_con=mod.parse_bpp_con(body), bpp_ind=mod.parse_bpp_ind(body),
            dre_con=mod.parse_dre_con(body), dre_ind=mod.parse_dre_ind(body),
            dfc_con=tuple(rows),
        )

    monkeypatch.setattr(CvmDfpHTTPHarvester, "fetch", fake_fetch)


def _live(monkeypatch, **kwargs):
    monkeypatch.setattr(
        BolsaiHTTPHarvester,
        "fetch",
        lambda self, target: FetchedFundamentals(
            target=target, status_code=200,
            fundamentals=make_bolsai_fundamentals(
                shares_outstanding=1_000_000_000.0, close_price=10.0, dividend_yield=None
            ),
        ),
    )
    return fetch_equity_template_live(
        "KLBN4", NON_FINANCIAL_CNPJ, 2025, "fake-key", None, **kwargs
    )


def test_template_fills_payout_ratio_percent(monkeypatch):
    _mock_dfp_years(monkeypatch, {2025: 957000.0})

    template, resultado = _live(monkeypatch)

    # 957 mi paid / 1,678 mi net income (fixture DRE: 1_678_211 thousand)
    assert template["financials"]["payout_ratio"] == pytest.approx(57.03, abs=0.01)
    assert "payout_ratio" in resultado.fetched_fields


def test_template_counts_five_paying_years_reading_each_year_from_its_own_file(monkeypatch):
    calls = []
    _mock_dfp_years(monkeypatch, dict.fromkeys(range(2021, 2026), 1000.0), calls=calls)

    template, resultado = _live(monkeypatch)

    assert template["financials"]["dividend_consistency_years"] == 5
    assert "dividend_consistency_years" in resultado.fetched_fields
    assert any("pelo menos 5" in w for w in resultado.warnings)
    # one file per year of the 5-year window, each downloaded once (ano-3 is
    # shared with the growth baseline).
    assert sorted(calls) == [2021, 2022, 2023, 2024, 2025]


def test_template_streak_stops_at_a_year_that_paid_nothing(monkeypatch):
    _mock_dfp_years(
        monkeypatch, {2025: 1000.0, 2024: 1000.0, 2023: 0.0, 2022: 1000.0, 2021: 1000.0}
    )

    template, _ = _live(monkeypatch)

    assert template["financials"]["dividend_consistency_years"] == 2


def test_template_missing_history_file_warns_and_never_assumes_a_paid_year(monkeypatch):
    _mock_dfp_years(monkeypatch, dict.fromkeys(range(2021, 2026), 1000.0), fail_years=(2023,))

    template, resultado = _live(monkeypatch)

    assert template["financials"]["dividend_consistency_years"] == 2  # 2025, 2024 only
    assert any("2023" in w and "histórico de dividendos" in w for w in resultado.warnings)


def test_template_without_a_current_year_dividend_line_leaves_streak_unset(monkeypatch):
    _mock_dfp_years(monkeypatch, {2024: 1000.0, 2023: 1000.0})  # nothing for 2025

    template, resultado = _live(monkeypatch)

    # the key exists as an analyzer default; what matters is it was not "fetched"
    assert "dividend_consistency_years" not in resultado.fetched_fields
    assert template["financials"]["dividend_consistency_years"] == 0  # default untouched


def test_template_uses_a_shared_dfp_harvester_when_given(monkeypatch):
    seen = []
    _mock_dfp_years(monkeypatch, {2025: 1000.0})

    class Recorder:
        def fetch(self, target):
            seen.append(target.ano)
            return CvmDfpHTTPHarvester.fetch(None, target)  # the mocked class-level fetch

    _live(monkeypatch, dfp_harvester=Recorder())

    assert sorted(seen) == [2021, 2022, 2023, 2024, 2025]


def test_shared_dfp_cache_downloads_each_year_once_across_equities(monkeypatch):
    from iip.sources.cvm_dfp_harvester import active_dfp_cache, shared_dfp_cache

    calls = []
    _mock_dfp_years(monkeypatch, dict.fromkeys(range(2021, 2026), 1000.0), calls=calls)

    assert active_dfp_cache() is None
    with shared_dfp_cache():
        assert active_dfp_cache() is not None
        _live(monkeypatch)
        _live(monkeypatch)  # a second equity of the same run
        _live(monkeypatch)
    assert active_dfp_cache() is None  # scoped: not leaked past the block

    assert sorted(calls) == [2021, 2022, 2023, 2024, 2025]  # 5 files for 3 equities, not 15


def test_without_the_shared_cache_each_equity_downloads_on_its_own(monkeypatch):
    calls = []
    _mock_dfp_years(monkeypatch, dict.fromkeys(range(2021, 2026), 1000.0), calls=calls)

    _live(monkeypatch)
    _live(monkeypatch)

    assert len(calls) == 10  # 5 files per equity, twice


def test_decorator_scopes_the_cache_to_the_batch_call(monkeypatch):
    from iip.sources.cvm_dfp_harvester import active_dfp_cache, with_shared_dfp_cache

    @with_shared_dfp_cache
    def batch():
        return active_dfp_cache()

    assert batch() is not None
    assert active_dfp_cache() is None


def test_template_flags_a_zero_year_between_paying_years(monkeypatch):
    # ABCB4 in the real data: 2025 paid, 2024 reported 0, 2023..2021 paid.
    _mock_dfp_years(
        monkeypatch, {2025: 1000.0, 2024: 0.0, 2023: 1000.0, 2022: 1000.0, 2021: 1000.0}
    )

    template, resultado = _live(monkeypatch)

    assert template["financials"]["dividend_consistency_years"] == 1
    assert any("parou em 2024" in w and "confira" in w for w in resultado.warnings)


def test_template_does_not_flag_a_genuine_lapse_with_nothing_paid_before(monkeypatch):
    _mock_dfp_years(monkeypatch, {2025: 1000.0, 2024: 1000.0, 2023: 0.0, 2022: 0.0, 2021: 0.0})

    template, resultado = _live(monkeypatch)

    assert template["financials"]["dividend_consistency_years"] == 2
    assert not any("parou em" in w for w in resultado.warnings)
