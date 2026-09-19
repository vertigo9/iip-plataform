"""Vacância lida do relatório gerencial da gestora (TRXF11, BTLG11, HGBS11).

Os trechos de texto abaixo foram capturados dos PDFs reais de 19/09/2026 (texto
do pypdf), preservando a ordem em que o pypdf os devolve."""

import pytest

from iip.cli.fetch_template import _enrich_fii_with_vacancia_report
from iip.sources.fii_vacancia import (
    VacanciaReading,
    latest_hedge_url,
    latest_trx_url,
    parse_btg,
    parse_hedge,
    parse_trx,
    profile_for_ticker,
)
from iip.sources.fii_vacancia_harvester import (
    FetchedVacancia,
    FiiVacanciaHTTPHarvester,
)

TRX_TEXT = """Educational: BRL 5,769.01, Hospital: BRL
23,562.93 and Shopping Mall: BRL
6,086.60
Vacancy
Physical 0.67% and Financial 0.42%
Decathlon
Joinville/SCTRX Real Estate REIT"""

BTG_TEXT = """RETORNO
 BTLG
 VS IFIX
 (2026)
4,0% VS 1,1%
VACÂNCIA FINANCEIRA
1,2%
COTISTAS
515.243
VOLUME MENSAL"""

HEDGE_TEXT = (
    "em comparação ao mesmo período de 2025.\n"
    "VACÂNCIA: O Fundo encerrou jul/26 com 4,4% da ABL vaga vs. 4,4% em jun/26 "
    "e 5,0% em jun/25.\n"
    "NOI/m²: Em julho, o NOI/m² do Fundo foi de R$ 87,2/m²"
)


def test_trx_reads_both_measures_and_prefers_financial():
    reading = parse_trx(TRX_TEXT)
    assert reading.physical_vacancy_pct == 0.67
    assert reading.financial_vacancy_pct == 0.42
    assert reading.basis == "financeira"
    assert reading.occupancy_rate == pytest.approx(0.9958)


def test_btg_reads_financial_vacancy_after_its_label():
    reading = parse_btg(BTG_TEXT)
    assert reading.financial_vacancy_pct == 1.2
    assert reading.physical_vacancy_pct is None
    assert reading.occupancy_rate == pytest.approx(0.988)


def test_hedge_reads_physical_vacancy_and_reference_month():
    reading = parse_hedge(HEDGE_TEXT)
    assert reading.physical_vacancy_pct == 4.4
    assert reading.financial_vacancy_pct is None
    assert reading.reference == "jul/26"
    assert reading.basis == "física"
    assert reading.occupancy_rate == pytest.approx(0.956)


@pytest.mark.parametrize("parser", [parse_trx, parse_btg, parse_hedge])
def test_parsers_return_none_when_layout_does_not_match(parser):
    assert parser("Relatório sem a seção de vacância") is None
    assert parser("") is None


def test_parsers_refuse_a_value_outside_0_to_100():
    assert parse_btg("VACÂNCIA FINANCEIRA 120,0%") is None
    assert (
        parse_trx("Vacancy Physical 0.5% and Financial 140.00%").physical_vacancy_pct
        == 0.5
    )
    assert (
        parse_trx("Vacancy Physical 0.5% and Financial 140.00%").financial_vacancy_pct
        is None
    )


def test_btg_ignores_a_vacancy_label_without_a_percentage_after_it():
    assert parse_btg("Vacância financeira do portfólio\nvalor a definir") is None


def test_latest_trx_url_uses_the_upload_folder_not_the_file_name():
    urls = [
        "https://www.trxf11.com.br/wp-content/uploads/2026/07/Investor-Report-06.2026.pdf",
        "https://www.trxf11.com.br/wp-content/uploads/2026/08/TRXF11-Investor-Report-July-2026.pdf",
        "https://www.trxf11.com.br/wp-content/uploads/2026/05/Investor-Report-April-2026.pdf",
        "https://www.trxf11.com.br/wp-content/uploads/2025/11/Lamina-TRXF11_Setembro25.pdf",
    ]
    assert latest_trx_url(urls) == urls[1]
    assert latest_trx_url(["https://x/y.pdf"]) is None


def test_latest_hedge_url_picks_the_newest_year_and_month():
    urls = [
        "https://h/arquivos/HGBS/Relatorio_Gestao/2026_08_HGBS_Relatorio.pdf",
        "https://h/arquivos/HGBS/Relatorio_Gestao/2026_07_HGBS_Relatorio.pdf",
        "https://h/arquivos/HGBS/Relatorio_Gestao/2025_12_HGBS_Relatorio.pdf",
        "https://h/arquivos/HGBS/Relatorio_Gestao/2026_08_HGBS_Fatos.pdf",
    ]
    assert latest_hedge_url(urls) == urls[0]


def test_only_verified_layouts_have_a_profile():
    assert {
        t
        for t in ("TRXF11", "BTLG11", "HGBS11", "XPML11", "KNRI11")
        if profile_for_ticker(t)
    } == {"TRXF11", "BTLG11", "HGBS11"}
    assert profile_for_ticker(" btlg11 ") is not None


def test_harvester_returns_none_without_a_profile_and_never_downloads():
    def opener(*args, **kwargs):
        raise AssertionError("no network for a ticker without a profile")

    assert FiiVacanciaHTTPHarvester(opener).fetch("XPML11") is None


def _stub_fetch(monkeypatch, result):
    monkeypatch.setattr(FiiVacanciaHTTPHarvester, "fetch", lambda self, ticker: result)


def test_enrichment_fills_occupancy_rate_from_financial_vacancy(monkeypatch):
    reading = VacanciaReading("btg_relatorio_gerencial", financial_vacancy_pct=1.2)
    _stub_fetch(monkeypatch, FetchedVacancia("BTLG11", "https://r.pdf", reading))
    financials, fetched, warnings = _enrich_fii_with_vacancia_report(
        {"occupancy_rate": 0.9}, "BTLG11"
    )
    assert financials["occupancy_rate"] == pytest.approx(0.988)
    assert fetched == ["occupancy_rate"]
    assert warnings == []


def test_enrichment_flags_when_only_the_physical_vacancy_is_available(monkeypatch):
    reading = VacanciaReading("hedge_relatorio_gestao", physical_vacancy_pct=4.4)
    _stub_fetch(monkeypatch, FetchedVacancia("HGBS11", "https://r.pdf", reading))
    financials, fetched, warnings = _enrich_fii_with_vacancia_report({}, "HGBS11")
    assert financials["occupancy_rate"] == pytest.approx(0.956)
    assert fetched == ["occupancy_rate"]
    assert len(warnings) == 1 and "física" in warnings[0]


def test_enrichment_keeps_the_default_and_warns_when_layout_changed(monkeypatch):
    _stub_fetch(monkeypatch, FetchedVacancia("TRXF11", "https://r.pdf", None))
    financials, fetched, warnings = _enrich_fii_with_vacancia_report(
        {"occupancy_rate": 0.9}, "TRXF11"
    )
    assert financials == {"occupancy_rate": 0.9}
    assert fetched == []
    assert "layout" in warnings[0]


def test_enrichment_never_raises_when_the_download_fails(monkeypatch):
    def boom(self, ticker):
        raise OSError("sem rede")

    monkeypatch.setattr(FiiVacanciaHTTPHarvester, "fetch", boom)
    financials, fetched, warnings = _enrich_fii_with_vacancia_report(
        {"occupancy_rate": 0.9}, "TRXF11"
    )
    assert financials == {"occupancy_rate": 0.9}
    assert fetched == []
    assert "sem rede" in warnings[0]


def test_enrichment_is_a_silent_no_op_for_a_ticker_without_a_profile():
    assert _enrich_fii_with_vacancia_report({"a": 1}, "XPML11") == ({"a": 1}, [], [])
