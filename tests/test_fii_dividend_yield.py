from types import SimpleNamespace

import pytest

from iip.cli.fetch_template import _use_ttm_dividend_yield, fetch_fii_template_live
from iip.sources.b3_bolsai import BolsaiFiiData
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFii
from iip.sources.cvm_fii import FiiComplemento
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester, FetchedFiiReport

CNPJ = "11.839.593/0001-09"


def _mock_cvm(monkeypatch, monthly_yield):
    """One informe month, like a September run that has only the current year."""
    complementos = (
        FiiComplemento(
            cnpj_fundo_classe=CNPJ,
            data_referencia="2026-07-01",
            versao="1",
            valores={
                "Patrimonio_Liquido": 1_000_000_000.0,
                "Valor_Patrimonial_Cotas": 97.4,
                "Cotas_Emitidas": 10_000_000,
                "Percentual_Dividend_Yield_Mes": monthly_yield,
            },
        ),
    )
    monkeypatch.setattr(
        CvmFiiHTTPHarvester,
        "fetch",
        lambda self, target: FetchedFiiReport(
            target=target,
            status_code=200,
            geral=(),
            ativo_passivo=(),
            complemento=complementos,
        ),
    )


def _mock_bolsai(monkeypatch, **overrides):
    fields = {
        "ticker": "HGCR11",
        "name": "X",
        "reference_date": "2026-07-01",
        "close_price": 95.45,
        "book_value_per_share": 97.401459,
        "pvp": 0.98,
        "dividend_yield_ttm": 12.31,
        "net_asset_value": None,
        "shares_outstanding": None,
        "total_shareholders": None,
        "segment": "Outros",
        "management_type": "Ativa",
    }
    fields.update(overrides)
    monkeypatch.setattr(
        BolsaiHTTPHarvester,
        "fetch_fii",
        lambda self, target: FetchedFii(
            target=target, status_code=200, fii=BolsaiFiiData(**fields)
        ),
    )


def _live(monkeypatch, *, key="k"):
    return fetch_fii_template_live("HGCR11", CNPJ, 2026, key)


# --- the helper ---------------------------------------------------------------------


def test_helper_replaces_the_yield_with_the_12_month_figure():
    fii = SimpleNamespace(dividend_yield_ttm=12.31, reference_date="2026-07-01")

    financials, used, warning = _use_ttm_dividend_yield(
        {"dividend_yield": 0.9, "x": 1}, fii
    )

    assert used and financials == {"dividend_yield": 12.31, "x": 1}
    assert "12 meses" in warning and "2026-07-01" in warning


@pytest.mark.parametrize(
    "fii", [None, SimpleNamespace(dividend_yield_ttm=None, reference_date="x")]
)
def test_helper_keeps_the_existing_value_without_a_ttm(fii):
    original = {"dividend_yield": 0.9}

    financials, used, warning = _use_ttm_dividend_yield(original, fii)

    assert financials is original and not used and warning is None


# --- through fetch_fii_template_live -------------------------------------------------


def test_analyzer_yield_becomes_the_12_month_figure_and_the_partial_warning_goes_away(
    monkeypatch,
):
    _mock_cvm(monkeypatch, monthly_yield=0.0076)  # one month only
    _mock_bolsai(monkeypatch)

    template, result = _live(monkeypatch)

    assert template["financials"]["dividend_yield"] == 12.31
    assert result.dividend_yield_months_used == 12
    assert result.fetched_fields.count("dividend_yield") == 1
    assert not any(
        w.startswith("dividend_yield calculado com apenas") for w in result.warnings
    )
    assert any("TTM de 12 meses do bolsai" in w for w in result.warnings)


def test_a_cvm_zero_for_a_fund_that_distributes_no_longer_reaches_the_analyzer(
    monkeypatch,
):
    _mock_cvm(monkeypatch, monthly_yield=0.0)  # BTCI11/VGIP11/AFHI11 in the real data
    _mock_bolsai(monkeypatch, dividend_yield_ttm=13.95)

    template, _ = _live(monkeypatch)

    assert template["financials"]["dividend_yield"] == 13.95


def test_without_a_bolsai_yield_the_cvm_value_and_its_partial_warning_stay(monkeypatch):
    _mock_cvm(monkeypatch, monthly_yield=0.0076)
    _mock_bolsai(monkeypatch, dividend_yield_ttm=None)

    template, result = _live(monkeypatch)

    assert template["financials"]["dividend_yield"] == pytest.approx(0.76)
    assert result.dividend_yield_months_used == 1
    assert any(
        w.startswith("dividend_yield calculado com apenas 1") for w in result.warnings
    )


def test_without_a_bolsai_key_the_cvm_value_stays(monkeypatch):
    _mock_cvm(monkeypatch, monthly_yield=0.0076)

    template, result = _live(monkeypatch, key=None)

    assert template["financials"]["dividend_yield"] == pytest.approx(0.76)
    assert result.dividend_yield_months_used == 1
