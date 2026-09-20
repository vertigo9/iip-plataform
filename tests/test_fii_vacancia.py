"""Vacância lida do relatório gerencial da gestora (TRXF11, BTLG11, HGBS11, RBVA11,
KNRI11, HSML11, XPML11).

Os trechos de texto abaixo foram capturados dos PDFs reais de 19/09/2026 (texto
do pypdf), preservando a ordem em que o pypdf os devolve."""

import pytest

from iip.cli.fetch_template import _enrich_fii_with_vacancia_report
from iip.sources import hsi_mziq, xp_mziq
from iip.sources.fii_vacancia import (
    LeaseTermReading,
    VacanciaReading,
    latest_alianza_url,
    latest_hedge_url,
    latest_knri_url,
    latest_rbva_url,
    latest_trx_url,
    parse_alzr,
    parse_btg,
    parse_hedge,
    parse_hsi,
    parse_knri,
    parse_lease_alzr,
    parse_lease_knri,
    parse_lease_rbva,
    parse_lease_trx,
    parse_rbva,
    parse_trx,
    parse_xp,
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


RBVA_TEXT = """PRINCIPAIS NÚMEROS
74
 Imóveis
 299.783
m² ABL
8,3%
Vacância Física
2
 8
Inquilinos
R$
1,76
 bilhão
Patrimônio Líquido ¹
12,3%
Dividend Yield² anualizado"""

KNRI_TEXT = """Com relação a carteira de inquilinos do Fundo, tivemos a entrada da Galena, gestora
de recursos financeiros, no conjunto 71 do Edifício Joaquim Floriano, ocupando uma
área de 234 m².
Como resultado da movimentação acima, a vacância física2 ao final do mês de agosto
foi de 3,91% (ante 3,95% no mês anterior), a vacância financeira3 5,14% (ante 5,24% no
mês anterior) e a vacância financeira ajustada pelas carências previstas nos novos
contratos de locação 5,64% (ante 5,66% no mês anterior). Como mencionado acima,
após a concretização da venda do imóvel PIB Sumaré, os indicadores de vacância
sofrerão uma redução importante estimada em 2,17% (vacância física) e 0,74%
(vacância financeira)."""


# capturado na importação do módulo, antes de o conftest trocar o ``fetch`` por um stub
_REAL_FETCH = FiiVacanciaHTTPHarvester.fetch

HSI_TEXT = """HSI MallsFII - Relatório Gerencial – Agosto 2026
96,6% 96,7% 96,7% 96,6% 97,4% 97,2% 96,7% 96,8% 96,2% 96,3% 96,2% 96,4%
ago-25 set-25 out-25 nov-25 dez-25 jan-26 fev-26 mar-26 abr-26 mai-26 jun-26 jul-26
Taxa de Ocupação (%)
Notas: Considera contratos assinados e aprovados em comitê. Ponderada pela participação do Fundo nos shoppings."""

HSI_COST_CHART = """ago-25 set-25 out-25 nov-25 dez-25 jan-26 fev-26 mar-26 abr-26 mai-26
Custo de Ocupação (%)
2,9% 2,9% 4,4% 3,6%
-3,5%"""


XP_TEXT = """Indicadores
Operacionais Jul-26 Ano (2026) 12 meses
ABL Total (m2) 1.063.027   1.093.460  1.070.606
Custo de Ocupação médio (%) 11,7% 12,2% 11,9%
Descontos / Faturamento médio (%) 3,0% 3,1% 2,8%
Vacância (% ABL) média 4,7% 4,0% 3,9%
Inadimplência Líquida (%) 2,2% 2,5% 2,0%"""


# trechos reais do Relatório Gerencial do ALZR11 (agosto/2026): o bloco padrão, o
# Pueri Domus (participação via TSER11, "Área BOMA", 97%) e o de Sumaré (área de
# expansão). O resumo foi adaptado ao recorte: 3 ativos e a ABL somada.
ALZR_BLOCKS = """Classe do Imóvel Edifício Comercial Monousuário
Localização Del Castilho - Rio de Janeiro/RJ
Participação no Imóvel 100%
Área Bruta Locável 8.178m²
Área do Terreno 2.662m²
Contrato de Locação Atípico
Ocupação do Imóvel 100%
Valor do Aluguel Vigente R$ 350.000
Vencimento Julho/2026
Classe do Imóvel Edifício Comercial
Localização Alphaville - Barueri/SP
Participação no Imóvel 99,98% (através do fundo TSER11)
Área BOMA 19.026 m²
Contrato de Locação Atípico
Ocupação do Imóvel 97%
Valor do Aluguel Vigente R$ 2.067.044
Vencimento Setembro/2035
Classe do Imóvel Centro de Distribuição Logístico
Localização Sumaré/SP
Participação no Imóvel 100%
Área Bruta Locável 33.795m² + área de expansão de até 14.116m²
Área do Terreno 90.602m²
Contrato de Locação Atípico
Ocupação do Imóvel 100%
Valor do Aluguel Vigente R$ 918.676
Vencimento Julho/2039"""

ALZR_SUMMARY_FITS = "Indicadores Imobiliários Agosto 2026\nABL Total¹ 60.999 m²\nNúmero de Ativos¹ 3\nWALE 9,5 anos\n"
ALZR_TEXT = ALZR_SUMMARY_FITS + ALZR_BLOCKS
# ABL própria e ABL alugada dos 3 blocos acima, feitas à mão
ALZR_OWN_ABL = 8178 + 19026 * 0.9998 + 33795
ALZR_LEASED_ABL = 8178 + 19026 * 0.9998 * 0.97 + 33795


# trechos reais dos relatórios (agosto/2026) com o prazo médio declarado
LEASE_ALZR = """Indicadores Imobiliários Agosto 2026
ABL Total¹ 288.677 m²
Número de Ativos¹ 26
Número de Locatários¹ 20
WALE 9,5 anos
¹ Considera os ativos adquiridos na 8ª Emissão de Cotas: Fleury, BTS Shopee e"""

LEASE_TRX = """Revenue by Contract Type
Atypical 73.10% and Typical 26.90%
Wale
13.17 years
Asset Value per m²"""

LEASE_RBVA = """Valor de Mercado
6,4 anos
Wault⁴
R$
 1,75
 milhões
Volume médio diário"""

LEASE_KNRI = """RECEITA POR TIPO DE CONTRATO12 RECEITA POR ÍNDICE DE REAJUSTE
O Prazo Médio dos Contratos Firmados13 pelo Fundo é de 9,32 anos sendo de 7,86 anos para os escritórios e 11,61 anos
para os ativos logísticos. O Prazo Médio Remanescente14 dos contratos do fundo está em 2,72 anos, com 2,64 anos
para escritórios e 2,85 anos para ativos logísticos. Com datas de vencimento e de revisionais nos próximos anos"""


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


def test_rbva_reads_the_value_that_comes_before_its_label():
    reading = parse_rbva(RBVA_TEXT)
    assert reading.physical_vacancy_pct == 8.3
    assert reading.financial_vacancy_pct is None
    assert reading.basis == "física"
    assert reading.occupancy_rate == pytest.approx(0.917)


def test_knri_reads_physical_and_financial_and_ignores_the_adjusted_one():
    reading = parse_knri(KNRI_TEXT)
    assert reading.physical_vacancy_pct == 3.91
    assert reading.financial_vacancy_pct == 5.14  # not 5,64 (ajustada) nor 0,74
    assert reading.reference == "agosto"
    assert reading.basis == "financeira"
    assert reading.occupancy_rate == pytest.approx(0.9486)


def test_knri_tolerates_the_footnote_digit_glued_to_the_word():
    text = KNRI_TEXT.replace("física2", "física").replace("financeira3", "financeira")
    assert parse_knri(text).financial_vacancy_pct == 5.14


def test_rbva_does_not_read_a_percentage_from_prose_about_vacancy():
    prose = "a rescisão teve impacto marginal na vacância física, com 0,004% da ABL."
    assert parse_rbva(prose) is None


def test_hsi_reads_the_last_bar_of_the_occupancy_chart_as_physical_vacancy():
    reading = parse_hsi(HSI_TEXT)
    assert reading.physical_vacancy_pct == 3.6  # 100 - 96,4
    assert reading.financial_vacancy_pct is None
    assert reading.reference == "jul-26"
    assert reading.basis == "física"
    assert reading.occupancy_rate == pytest.approx(0.964)


def test_hsi_refuses_a_chart_whose_bars_and_months_do_not_line_up():
    eleven_months = HSI_TEXT.replace("ago-25 ", "")
    assert parse_hsi(eleven_months) is None


def test_hsi_does_not_read_the_neighbouring_occupancy_cost_chart():
    assert parse_hsi(HSI_COST_CHART) is None


def test_xp_reads_the_month_column_of_the_abl_vacancy_row():
    reading = parse_xp(XP_TEXT)
    assert reading.physical_vacancy_pct == 4.7  # not 4,0 (ano) nor 3,9 (12 meses)
    assert reading.financial_vacancy_pct is None
    assert reading.reference == "jul-26"
    assert reading.basis == "física"
    assert reading.occupancy_rate == pytest.approx(0.953)


def test_xp_needs_the_column_header_to_trust_the_first_value():
    assert parse_xp(XP_TEXT.replace("Jul-26 Ano (2026) 12 meses", "12 meses")) is None


def test_xp_ignores_a_vacancy_row_that_comes_before_the_header():
    row = "Vacância (% ABL) média 4,7% 4,0% 3,9%"
    header = "Operacionais Jul-26 Ano (2026) 12 meses"
    assert parse_xp(" ".join([row, header])) is None


def test_alzr_averages_the_property_occupancy_by_own_abl():
    reading = parse_alzr(ALZR_TEXT)
    expected_occupancy = ALZR_LEASED_ABL / ALZR_OWN_ABL
    assert reading.occupancy_rate == pytest.approx(expected_occupancy, abs=1e-5)
    assert reading.physical_vacancy_pct == pytest.approx(
        100 * (1 - expected_occupancy), abs=1e-3
    )
    assert reading.financial_vacancy_pct is None
    assert reading.basis == "física"
    assert reading.layout == "alianza_relatorio_gerencial"


def test_alzr_says_the_number_is_calculated_and_that_the_abl_does_not_add_up():
    text = ALZR_TEXT.replace("ABL Total¹ 60.999 m²", "ABL Total¹ 288.677 m²")
    note = parse_alzr(text).note
    assert "CALCULADA" in note and "3 imóveis" in note
    assert "60.999 m2" in note and "288.677 m2" in note
    assert "78.9% abaixo" in note  # (288.677 - 60.999) / 288.677


def test_alzr_note_says_so_when_the_abl_adds_up_with_the_declared_total():
    assert "confere com o ABL Total" in parse_alzr(ALZR_TEXT).note


def test_alzr_note_admits_when_the_report_gives_no_abl_total_to_check():
    text = ALZR_TEXT.replace("ABL Total¹ 60.999 m²\n", "")
    assert "não traz o ABL Total" in parse_alzr(text).note


def test_alzr_refuses_when_the_annex_does_not_have_every_declared_asset():
    assert (
        parse_alzr(ALZR_TEXT.replace("Número de Ativos¹ 3", "Número de Ativos¹ 4"))
        is None
    )


def test_alzr_refuses_when_the_summary_has_no_asset_count():
    assert parse_alzr(ALZR_TEXT.replace("Número de Ativos¹ 3\n", "")) is None


def test_alzr_refuses_a_block_it_cannot_read_completely():
    # sem a área, o bloco do Pueri Domus não pode entrar na média: nada, e não uma
    # média dos outros dois (que daria 100%)
    assert parse_alzr(ALZR_TEXT.replace("Área BOMA 19.026 m²\n", "")) is None


def test_alzr_refuses_an_occupancy_outside_0_to_100():
    assert (
        parse_alzr(
            ALZR_TEXT.replace("Ocupação do Imóvel 97%", "Ocupação do Imóvel 197%")
        )
        is None
    )


ALZR_HOME = """
<li><a href="https://fnet.bmfbovespa.com.br/fnet/publico/visualizarDocumento?id=1324003&amp;cvm=true">18/09/2026 - Divulgação de Rendimentos - Ago/26</a></li>
<li><a href="Download.aspx?Arquivo=B2TQ5L8Ciu82/qFuvgdWow==">18/09/2026 - Relatório Gerencial - Ago/26</a></li>
<li><a href="Download.aspx?Arquivo=DikPe2j4ygJkucvmZVSmjA==">17/09/2026 - Carta aos Cotistas - Rebalanceamento</a></li>
<li><a href="Download.aspx?Arquivo=ANTIGO12345==">18/08/2026 - Relatório Gerencial - Jul/26</a></li>
"""


def test_latest_alianza_url_takes_the_newest_management_report_link():
    url = latest_alianza_url(ALZR_HOME, "https://alzr11.alianza.com.br/")
    assert (
        url
        == "https://alzr11.alianza.com.br/Download.aspx?Arquivo=B2TQ5L8Ciu82/qFuvgdWow=="
    )


def test_latest_alianza_url_ignores_other_documents_and_pages_without_a_report():
    assert (
        latest_alianza_url(
            "<a href='x.pdf'>18/09/2026 - Relatório Gerencial</a>", "https://a/"
        )
        is None
    )
    only_letter = (
        '<a href="Download.aspx?Arquivo=Z==">17/09/2026 - Carta aos Cotistas</a>'
    )
    assert latest_alianza_url(only_letter, "https://a/") is None


@pytest.mark.parametrize(
    "parser",
    [
        parse_trx,
        parse_btg,
        parse_hedge,
        parse_rbva,
        parse_knri,
        parse_hsi,
        parse_xp,
        parse_alzr,
    ],
)
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


def test_latest_rbva_url_takes_the_newest_date_then_the_higher_serial():
    urls = [
        "https://docs.riobravo.com.br/RBVA11/relatorios/relatorios-2026-07-31-1294479.pdf",
        "https://docs.riobravo.com.br/RBVA11/relatorios/relatorios-2026-07-31-1313146.pdf",
        "https://docs.riobravo.com.br/RBVA11/relatorios/relatorios-2026-08-31-1321749.pdf",
        "https://docs.riobravo.com.br/RBVA11/informes/informe-2026-09-30-1400000.pdf",
    ]
    assert latest_rbva_url(urls) == urls[2]
    assert latest_rbva_url(urls[:2]) == urls[1]
    assert latest_rbva_url([urls[3]]) is None


def test_latest_knri_url_picks_the_newest_carta_do_gestor():
    urls = [
        "https://www.kinea.com.br/wp-content/uploads/2026/08/KNRI_Carta-do-Gestor_07-2026.pdf",
        "https://www.kinea.com.br/wp-content/uploads/2026/09/KNRI_Carta-do-Gestor_08-2026.pdf",
        "https://www.kinea.com.br/wp-content/uploads/2025/12/KNRI_Carta-do-Gestor_11-2025.pdf",
        "https://www.kinea.com.br/wp-content/uploads/2026/09/KNRI_Aviso-aos-Cotistas_08-2026.pdf",
    ]
    assert latest_knri_url(urls) == urls[1]
    assert latest_knri_url([urls[3]]) is None


def test_only_verified_layouts_have_a_profile():
    assert {
        t
        for t in (
            "TRXF11",
            "BTLG11",
            "HGBS11",
            "RBVA11",
            "KNRI11",
            "HSML11",
            "XPML11",
            "ALZR11",
            "HGRU11",
        )
        if profile_for_ticker(t)
    } == {
        "TRXF11",
        "BTLG11",
        "HGBS11",
        "RBVA11",
        "KNRI11",
        "HSML11",
        "XPML11",
        "ALZR11",
    }
    assert profile_for_ticker(" btlg11 ") is not None


def test_harvester_returns_none_without_a_profile_and_never_downloads(monkeypatch):
    # o conftest troca ``fetch`` por um stub; aqui vale a implementação real
    monkeypatch.setattr(FiiVacanciaHTTPHarvester, "fetch", _REAL_FETCH)

    def opener(*args, **kwargs):
        raise AssertionError("no network for a ticker without a profile")

    assert FiiVacanciaHTTPHarvester(opener).fetch("HGRU11") is None


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
    assert _enrich_fii_with_vacancia_report({"a": 1}, "HGRU11") == ({"a": 1}, [], [])


def test_hsi_mziq_config_is_registered_for_hsml11_only():
    fund = hsi_mziq.fund_for_ticker(" hsml11 ")
    assert fund.company_id == "1bea7b91-2f45-4c39-99ab-5856eff6841b"
    assert "relatorio-gerencial" in fund.category_internal_names
    assert hsi_mziq.fund_for_ticker("BTLG11") is None
    with pytest.raises(ValueError):
        hsi_mziq.build_years_target("BTLG11")


def _mziq_doc(category, date, url, *, published=True):
    from iip.sources.mziq import MziqDocument

    return MziqDocument(
        id=url,
        company_id="c",
        file_name_original=None,
        file_title=None,
        url=url,
        file_size=None,
        file_date=date,
        file_quarter=None,
        file_year=int(date[:4]),
        category=category,
        is_published=published,
    )


def _patch_mziq(monkeypatch, docs_by_year):
    from iip.sources.mziq_harvester import MziqHTTPHarvester

    monkeypatch.setattr(
        MziqHTTPHarvester, "fetch_years", lambda self, target: tuple(docs_by_year)
    )
    monkeypatch.setattr(
        MziqHTTPHarvester,
        "fetch_documents",
        lambda self, target: docs_by_year[int(target.body["year"])],
    )


@pytest.mark.parametrize(
    "ticker, category",
    [
        ("HSML11", "relatorio-gerencial"),
        ("BTLG11", "relatorios_gerenciais"),
        ("XPML11", "relatorios_gerenciais"),
    ],
)
def test_latest_mziq_report_uses_each_managers_category_and_the_newest_published(
    monkeypatch, ticker, category
):
    _patch_mziq(
        monkeypatch,
        {
            2026: [
                _mziq_doc(category, "2026-07-08T00:00:00.000Z", "https://r/jul.pdf"),
                _mziq_doc(category, "2026-09-08T00:00:00.000Z", "https://r/ago.pdf"),
                _mziq_doc(
                    category,
                    "2026-10-08T00:00:00.000Z",
                    "https://r/rascunho.pdf",
                    published=False,
                ),
                _mziq_doc("xml-5.0", "2026-09-30T00:00:00.000Z", "https://r/xml.pdf"),
            ],
        },
    )
    assert FiiVacanciaHTTPHarvester()._latest_mziq_url(ticker) == "https://r/ago.pdf"


def test_latest_mziq_report_falls_back_to_the_previous_year(monkeypatch):
    _patch_mziq(
        monkeypatch,
        {
            2026: [_mziq_doc("xml-5.0", "2026-01-01T00:00:00.000Z", "https://r/x.pdf")],
            2025: [
                _mziq_doc(
                    "relatorio-gerencial",
                    "2025-12-08T00:00:00.000Z",
                    "https://r/dez.pdf",
                )
            ],
        },
    )
    assert FiiVacanciaHTTPHarvester()._latest_mziq_url("HSML11") == "https://r/dez.pdf"


def test_xp_mziq_config_is_registered_for_xpml11_only():
    fund = xp_mziq.fund_for_ticker("xpml11")
    assert fund.company_id == "8071264f-09a1-481e-9c5e-25e5b370cd63"
    assert fund.category_internal_names == ("relatorios_gerenciais",)
    assert xp_mziq.fund_for_ticker("HSML11") is None
    with pytest.raises(ValueError):
        xp_mziq.build_documents_target("HSML11", 2026)


def test_enrichment_shows_the_note_of_a_calculated_occupancy(monkeypatch):
    reading = parse_alzr(ALZR_TEXT)
    _stub_fetch(monkeypatch, FetchedVacancia("ALZR11", "https://r.pdf", reading))
    financials, fetched, warnings = _enrich_fii_with_vacancia_report({}, "ALZR11")
    assert financials["occupancy_rate"] == pytest.approx(reading.occupancy_rate)
    assert fetched == ["occupancy_rate"]
    assert any("vacância física" in w for w in warnings)  # a base
    assert any("occupancy_rate: ocupação CALCULADA" in w for w in warnings)  # o método


def test_each_manager_lease_term_is_read_with_the_label_the_report_uses():
    assert parse_lease_alzr(LEASE_ALZR) == LeaseTermReading(9.5, "WALE")
    assert parse_lease_trx(LEASE_TRX) == LeaseTermReading(13.17, "WALE")
    assert parse_lease_rbva(LEASE_RBVA) == LeaseTermReading(6.4, "WAULT")
    assert parse_lease_knri(LEASE_KNRI) == LeaseTermReading(
        2.72, "Prazo Médio Remanescente"
    )


def test_knri_takes_the_remaining_term_and_never_the_total_contract_duration():
    reading = parse_lease_knri(LEASE_KNRI)
    assert reading.years == 2.72  # not 9,32 (contratos firmados), 7,86 nor 11,61


def test_knri_refuses_a_text_with_only_the_total_contract_duration():
    only_total = (
        "O Prazo Médio dos Contratos Firmados13 pelo Fundo é de 9,32 anos sendo de "
        "7,86 anos para os escritórios e 11,61 anos para os ativos logísticos."
    )
    assert parse_lease_knri(only_total) is None


@pytest.mark.parametrize(
    "parser",
    [parse_lease_alzr, parse_lease_trx, parse_lease_rbva, parse_lease_knri],
)
def test_lease_parsers_return_none_when_the_report_does_not_declare_it(parser):
    assert parser("Relatório sem prazo médio declarado") is None
    assert parser("") is None


@pytest.mark.parametrize("years", ["0,0", "80,0"])
def test_a_lease_term_outside_a_plausible_range_is_refused(years):
    assert parse_lease_alzr(f"WALE {years} anos") is None


def test_only_the_four_clear_declarations_have_a_lease_parser():
    with_parser = {
        t
        for t in (
            "TRXF11",
            "BTLG11",
            "HGBS11",
            "RBVA11",
            "KNRI11",
            "HSML11",
            "XPML11",
            "ALZR11",
        )
        if profile_for_ticker(t).lease_parser is not None
    }
    # BTLG11: o "WAULT 5 anos" está dentro de um gráfico de vencimentos, arredondado e
    # sem definição; os shoppings (HGBS11, HSML11, XPML11) não declaram prazo
    assert with_parser == {"TRXF11", "RBVA11", "KNRI11", "ALZR11"}


def test_enrichment_fills_the_lease_term_and_says_which_label_it_came_from(
    monkeypatch,
):
    occupancy = VacanciaReading("kinea_carta_do_gestor", financial_vacancy_pct=5.14)
    lease = LeaseTermReading(2.72, "Prazo Médio Remanescente")
    _stub_fetch(
        monkeypatch, FetchedVacancia("KNRI11", "https://r.pdf", occupancy, lease)
    )
    financials, fetched, warnings = _enrich_fii_with_vacancia_report({}, "KNRI11")
    assert financials["avg_lease_term_years"] == 2.72
    assert fetched == ["occupancy_rate", "avg_lease_term_years"]
    assert any(
        "avg_lease_term_years = 2.72 anos" in w and "Prazo Médio Remanescente" in w
        for w in warnings
    )


def test_enrichment_fills_the_lease_term_even_when_the_occupancy_layout_changed(
    monkeypatch,
):
    lease = LeaseTermReading(9.5, "WALE")
    _stub_fetch(monkeypatch, FetchedVacancia("ALZR11", "https://r.pdf", None, lease))
    financials, fetched, warnings = _enrich_fii_with_vacancia_report(
        {"occupancy_rate": 0.85}, "ALZR11"
    )
    assert financials == {"occupancy_rate": 0.85, "avg_lease_term_years": 9.5}
    assert fetched == ["avg_lease_term_years"]
    assert "layout" in warnings[0]


def test_enrichment_leaves_the_lease_term_alone_when_the_report_declares_none(
    monkeypatch,
):
    occupancy = VacanciaReading("btg_relatorio_gerencial", financial_vacancy_pct=1.2)
    _stub_fetch(monkeypatch, FetchedVacancia("BTLG11", "https://r.pdf", occupancy))
    financials, fetched, _ = _enrich_fii_with_vacancia_report(
        {"avg_lease_term_years": 5}, "BTLG11"
    )
    assert financials["avg_lease_term_years"] == 5
    assert fetched == ["occupancy_rate"]
