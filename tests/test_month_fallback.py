from urllib.error import HTTPError

import pytest

from iip.cli.fetch_template import (
    _fetch_month_with_fallback,
    fetch_etf_template_live,
    fetch_fixed_income_template_live,
)
from iip.sources.cvm_renda_fixa import InformeDiario
from iip.sources.cvm_renda_fixa_harvester import (
    CvmRendaFixaHTTPHarvester,
    FetchedDiario,
)

CNPJ = "45.121.022/0001-48"


def _http_error(code):
    return HTTPError("https://dados.cvm.gov.br/x", code, "err", None, None)


class _Target:
    def __init__(self, ano, mes):
        self.ano, self.mes = ano, mes


def _fetch_failing(months_missing):
    tried = []

    def fetch(target):
        tried.append((target.ano, target.mes))
        if (target.ano, target.mes) in months_missing:
            raise _http_error(404)
        return "ok"

    fetch.tried = tried
    return fetch


def test_helper_returns_requested_month_without_warning_when_available():
    fetch = _fetch_failing(set())
    result, warning = _fetch_month_with_fallback(fetch, _Target, 2026, 9, "Informe")
    assert (result, warning) == ("ok", None)
    assert fetch.tried == [(2026, 9)]


def test_helper_steps_back_and_names_the_month_used():
    fetch = _fetch_failing({(2026, 9)})
    result, warning = _fetch_month_with_fallback(
        fetch, _Target, 2026, 9, "Informe Diário"
    )
    assert result == "ok"
    assert fetch.tried == [(2026, 9), (2026, 8)]
    assert (
        warning
        == "Informe Diário de 2026-09 ainda não publicado pela CVM; usando 2026-08."
    )


def test_helper_crosses_the_year_boundary_and_stops_after_two_months_back():
    fetch = _fetch_failing({(2026, 1), (2025, 12)})
    _fetch_month_with_fallback(fetch, _Target, 2026, 1, "Informe")
    assert fetch.tried == [(2026, 1), (2025, 12), (2025, 11)]

    fetch = _fetch_failing({(2026, 1), (2025, 12), (2025, 11)})
    with pytest.raises(HTTPError) as exc:
        _fetch_month_with_fallback(fetch, _Target, 2026, 1, "Informe")
    assert exc.value.code == 404
    assert len(fetch.tried) == 3


def test_helper_does_not_swallow_other_http_errors():
    def fetch(target):
        raise _http_error(500)

    with pytest.raises(HTTPError) as exc:
        _fetch_month_with_fallback(fetch, _Target, 2026, 9, "Informe")
    assert exc.value.code == 500


def _diario_fetch_missing_current_month(tried):
    def fetch_diario(self, target):
        tried.append((target.ano, target.mes))
        if (target.ano, target.mes) == (2026, 9):
            raise _http_error(404)
        informe = InformeDiario(
            tipo_fundo_classe="CLASSE FIF/FAPI",
            cnpj_fundo_classe=CNPJ,
            id_subclasse=None,
            data_competencia="2026-08-31",
            valor_total=15_000_000.0,
            valor_cota=1.89,
            patrimonio_liquido=14_800_000.0,
            captacao_dia=0.0,
            resgate_dia=0.0,
            numero_cotistas=10,
        )
        return FetchedDiario(target=target, status_code=200, informes=(informe,))

    return fetch_diario


def test_fixed_income_fetch_falls_back_to_previous_month(monkeypatch):
    tried = []
    monkeypatch.setattr(
        CvmRendaFixaHTTPHarvester,
        "fetch_diario",
        _diario_fetch_missing_current_month(tried),
    )

    template, resultado = fetch_fixed_income_template_live("CDII11", CNPJ, 2026, 9)

    assert tried == [(2026, 9), (2026, 8)]
    assert template["financials"]["assets_under_management_millions"] == 14.8
    assert any("2026-09" in w and "2026-08" in w for w in resultado.warnings)


def test_etf_fetch_falls_back_to_previous_month(monkeypatch):
    tried = []
    monkeypatch.setattr(
        CvmRendaFixaHTTPHarvester,
        "fetch_diario",
        _diario_fetch_missing_current_month(tried),
    )

    template, resultado = fetch_etf_template_live("BOVA11", CNPJ, 2026, 9, None)

    assert tried == [(2026, 9), (2026, 8)]
    assert template["financials"]["assets_under_management_millions"] == 14.8
    assert any("2026-09" in w and "2026-08" in w for w in resultado.warnings)
