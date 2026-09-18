"""Pátria's real-estate FII investor-relations documents via the MZIQ
platform (see ``iip.sources.mziq`` for the generic request/response
shapes) -- a lightweight, HTTP-only alternative to the Playwright-driven
``iip.harvest.patria`` scraper for document discovery/retrieval.

Each of Pátria's 5 funds turned out to have its OWN ``company_id`` on
MZIQ -- confirmed live only after this was initially assumed wrong.
A single UUID (``a49e77b8-0515-486d-80d7-ef7bb0ea4d32``) appears
identically in the raw page HTML of all 5 funds' own pages, which
looked at first like a shared tenant id; testing it against the real
API with each fund's own category names returned empty for 4 of them
-- it is genuinely just a shared page asset, not the MZIQ company_id,
except for PCIP11 (where it happens to also be the real company_id).
The other 4 funds' real ``company_id`` + category internal names were
only found by capturing actual network requests from a JS-rendered
page (Playwright), the same method ``iip.harvest.patria`` and
``reconhecer_mziq.py`` already use -- confirmed live (18/09/2026)
against each fund's own ``.../documentos/`` page. Category name lists
below are the exact captured arrays (each fund's own site queries all
of its categories in one request); a couple of blank ``""`` entries in
the real captured arrays were UI placeholders, dropped here since they
never match a real category. Two entries (HGRU11's and HGCR11's
"Planilha de Fundamentos") were captured as a human-readable label
instead of a slug -- likely a bug on Pátria's own site, not something
to guess a fix for -- kept verbatim; calls using them will just
resolve to no documents.

PCIP11's categories still use its OLD ticker "cvbi11" as their prefix
(the fund renamed from CVBI11 in 09/2025, see
``iip.portfolio.registry``'s note on this ticker) -- MZIQ's own CMS
was never updated to match, confirmed live.

Deliberately does NOT extract "cota patrimonial"/NAV: each fund's
"*_informe_contabil_mensal" PDF was opened and confirmed (18/09/2026)
to be the PDF rendering of the exact same CVM Anexo 39-I regulatory
filing ``iip.sources.cvm_fii`` already parses from CVM's own
structured CSV -- building a PDF parser here would duplicate that data
in a harder-to-parse format, not add anything CVM doesn't already
give. This module is for DOCUMENT retrieval (relatório de gestão,
fatos relevantes, apresentações, etc.), where it adds real coverage
CVM's dataset doesn't have.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatriaMziqFund:
    ticker: str
    company_id: str
    category_internal_names: tuple[str, ...]


PATRIA_MZIQ_FUNDS: dict[str, PatriaMziqFund] = {
    "HGRU11": PatriaMziqFund(
        ticker="HGRU11",
        company_id="666d4277-653c-4e97-81a4-731a48d886d2",
        category_internal_names=(
            "hgru_cshg_renda_urbana_fii_relatorios_ao_investidor",
            "hgru_cshg_renda_urbana_fii_fato_relevante",
            "hgru_cshg_renda_urbana_fii_apresentacoes",
            "hgru_cshg_renda_urbana_fii_informe_anual",
            "hgru_cshg_renda_urbana_fii_informe_trimestral",
            "hgru_cshg_renda_urbana_fii_informe_contabil_mensal",
            "hgru_cshg_renda_urbana_fii_comunicado_de_rendimentos",
            "hgru_cshg_renda_urbana_fii_assembleia_geral",
            "hgru_cshg_renda_urbana_fii_demonstracoes_financeiras",
            "hgru_cshg_renda_urbana_fii_regulamento",
            "hgru_cshg_renda_urbana_fii_arquivo_padronizado",
            "hgru_cshg_renda_urbana_fii_prospecto_e_emissao_1",
            "hgru_cshg_renda_urbana_fii_prospecto_e_emissao_2",
            "hgru_cshg_renda_urbana_fii_prospecto_e_emissao_3",
            "hgru_cshg_renda_urbana_fii_prospecto_e_emissao_4",
            "hgru_cshg_renda_urbana_fii_prospecto_e_emissao_5",
            "hgru_emissao_6",
            "hgru_emissao_7",
            "hgru_cshg_renda_urbana_fii_laudo_de_avaliacao_conclusao_de_negocio",
            "HGRU - Planilha de Fundamentos",  # captured verbatim -- see module docstring
        ),
    ),
    "LVBI11": PatriaMziqFund(
        ticker="LVBI11",
        company_id="ef0151fe-a22e-456d-8cc4-55ef365d7e3b",
        category_internal_names=(
            "lvbi11_relatorio_de_gestao",
            "lvbi11_fatos_relevantes",
            "lvbi11_comunicados_ao_mercado",
            "lvbi11_apresentacoes_trimestrais",
            "lvbi11_informe_anual",
            "lvbi11_informe_trimestral",
            "lvbi11_informe_contabil_mensal",
            "lvbi11_assembleias",
            "lvbi11_demonstracoes_financeiras",
            "lvbi11_arquivos_xml",
            "lvbi11_emissoes_de_cotas",
            "lvbi11_laudo_de_avaliacao",
            "lvbi11_planilha_de_fundamentos",
            "lvbi11_rendimentos",
            "lvbi-regulamento",
        ),
    ),
    "HGCR11": PatriaMziqFund(
        ticker="HGCR11",
        company_id="8700340f-de5f-46d7-bbc7-83b2105cdd34",
        category_internal_names=(
            "hgcr_cshg_recebiveis_imobiliarios_fii_relatorios_ao_investidor",
            "hgcr_cshg_recebiveis_imobiliarios_fii_fatos_relevantes",
            "hgcr_cshg_recebiveis_imobiliarios_fii_apresentacoes",
            "hgcr_cshg_recebiveis_imobiliarios_fii_informe_anual",
            "hgcr_cshg_recebiveis_imobiliarios_fii_informe_trimestral",
            "hgcr_cshg_recebiveis_imobiliarios_fii_informe_contabil_mensal",
            "hgcr_cshg_recebiveis_imobiliarios_fii_comunicado_de_rendimentos",
            "hgcr_cshg_recebiveis_imobiliarios_fii_assembleia_geral",
            "hgcr_cshg_recebiveis_imobiliarios_fii_demonstracoes_financeiras",
            "hgcr_cshg_recebiveis_imobiliarios_fii_regulamento",
            "hgcr_cshg_recebiveis_imobiliarios_fii_arquivo_padronizado",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_1",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_2",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_3_Cancelada",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_3",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_4",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_5",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_6",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_7",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_8",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_8_2022",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_9_2022",
            "hgcr_cshg_recebiveis_imobiliarios_fii_prospecto_e_emissao_10_2022",
            "hgcr_cshg_recebiveis_imobiliarios_fii_demandas_judiciais",
            "HGCR11 - Planilha de Fundamentos",  # captured verbatim -- see module docstring
        ),
    ),
    "PVBI11": PatriaMziqFund(
        ticker="PVBI11",
        company_id="c1f32303-d1ca-40d4-95b0-5634247c7363",
        category_internal_names=(
            "pvbi11_relatorio_de_gestao",
            "pvbi11_fatos_relevantes",
            "pvbi11_comunicados_ao_mercado",
            "pvbi11_apresentacoes_trimestrais",
            "pvbi11_informes_anual",
            "pvbi11_informes_trimestral",
            "pvbi11_informes_contabil_mensal",
            "pvbi11_assembleias",
            "pvbi11_demonstracoes_financeiras",
            "pvbi11_arquivos_xml",
            "pvbi11_emissoes_de_cotas",
            "pvbi11_esg",
            "pvbi11_laudo_de_avaliacao",
            "pvbi11_planilha_de_fundamentos",
            "pvbi11_rendimento",
            "pvbi-regulamento",
        ),
    ),
    "PCIP11": PatriaMziqFund(
        ticker="PCIP11",
        company_id="a49e77b8-0515-486d-80d7-ef7bb0ea4d32",
        category_internal_names=(
            "cvbi11_relatorio_de_gestao",
            "cvbi11_fatos_relevantes",
            "cvbi11_comunicados_ao_mercado",
            "cvbi11_informe_anual",
            "cvbi11_informe_contabil_mensal",
            "cvbi11_informe_trimestral",
            "cvbi11_assembleias",
            "cvbi11_demonstracoes_financeiras",
            "cvbi11_arquivos_xml",
            "cvbi11_emissoes_de_cotas",
            "cvbi11_planilha_de_fundamentos",
            "cvbi11_rendimentos",
            "cvbi-regulamento",
        ),
    ),
}


def fund_for_ticker(ticker: str) -> PatriaMziqFund | None:
    return PATRIA_MZIQ_FUNDS.get(ticker.strip().upper())


def build_years_target(ticker: str):
    from .mziq import build_years_target as _build_years_target

    fund = fund_for_ticker(ticker)
    if fund is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_years_target(fund.company_id, fund.category_internal_names)


def build_documents_target(ticker: str, year: int):
    from .mziq import build_documents_target as _build_documents_target

    fund = fund_for_ticker(ticker)
    if fund is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_documents_target(fund.company_id, year, fund.category_internal_names)
