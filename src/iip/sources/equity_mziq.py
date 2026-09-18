"""Equity investor-relations documents via the MZIQ platform (see
``iip.sources.mziq`` for the generic request/response shapes) -- same
lightweight, HTTP-only approach as ``iip.sources.patria_mziq``/
``btg_mziq``, applied to the portfolio's equity registry positions.

ABCB4 (Banco ABC Brasil) confirmed live (18/09/2026, re-verified from
an earlier session's saved reconnaissance at
``mziq_reconhecimento/https_ri_abcbrasil_com_br_resultados_central_de_resultados/``)
-- its ``company_id``/categories were captured from real MZIQ API
traffic on https://ri.abcbrasil.com.br/resultados/central-de-resultados/.
This is also the concrete example ``iip.sources.mziq``'s own module
docstring already referenced as "confirmed live against ABC Brasil's
IR site" before any per-company config existed anywhere in the
codebase.

The other 13 portfolio equities were investigated (18/09/2026) via
plain HTTP only (no browser) -- each IR site's raw static HTML was
checked for an embedded ``company_id``/``fmId`` and a
``categories.push({...})`` list, then every found company_id was
independently re-verified live (POST to apicatalog.mziq.com, not just
trusted from the page). Result: 9 confirmed MZIQ-hosted, registered
below. The remaining 4 are confirmed NOT on MZIQ -- recorded here so a
future session doesn't repeat the same investigation:

  - ISAE4 (Isa Energia): custom ASP.NET MVC IR site, no "mziq" string
    anywhere in static HTML.
  - CPFE3 (CPFL Energia): proprietary idCanal-encoded CMS; the only
    "mziq" substring found was a coincidental fragment inside an
    unrelated base64-like URL parameter, not a real platform
    reference.
  - CMIG4 (Cemig): custom Next.js/Vercel site; zero "mziq" occurrences,
    and its CSP connect-src explicitly whitelists only a handful of
    unrelated domains (no mziq.com).
  - CSUD3 (CSU Digital): was on MZIQ before a Dec/2024 IR site
    relaunch; the current site runs a different platform entirely
    (``apiBaseUrl: "https://api.solutions-ir.com"``) -- old
    api.mziq.com document links only survive in stale search-engine
    caches from before the relaunch.

Each of these 4 would need its own separate, non-MZIQ provider to get
real document coverage -- not attempted here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquityMziqCompany:
    ticker: str
    company_id: str
    category_internal_names: tuple[str, ...]


EQUITY_MZIQ_COMPANIES: dict[str, EquityMziqCompany] = {
    "ABCB4": EquityMziqCompany(
        ticker="ABCB4",
        company_id="6298ef6f-2b75-43f8-b2ab-99e3fe33e809",
        category_internal_names=(
            "central-resultados-earnings-release",
            "central-resultados-dfp",
            "central-resultados-itr",
            "central-resultados-df-prudencial",
            "central-resultados-df",
            "central-resultados-apresentacao",
            "central-resultados-fact-sheet",
            "central-resultados-teleconferencia-slides",
            "central-resultados-teleconferencia",
            "central-resultados-transcricao",
            "central-resultados-series-historicas",
        ),
    ),
    "BBSE3": EquityMziqCompany(
        ticker="BBSE3",
        company_id="d4ee6df5-1dd8-4fb5-b518-e05397c304e4",
        category_internal_names=(
            "central_analise_do_desempenho_",
            "central_apresentacao_de_resultado_",
            "central_audio_da_teleconferencia_",
            "central_demonstracoes_contabeis_.docx",
            "central_demonstracoes_contabeis_.pdf",
            "central_series_historicas",
            "central_sumario_do_desempenho_",
            "central_transcricao",
        ),
    ),
    "CXSE3": EquityMziqCompany(
        ticker="CXSE3",
        company_id="3972906b-e50b-4f74-ab74-4d0d32125d11",
        category_internal_names=(
            "central-resultados-apresentacao",
            "central-resultados-audio",
            "central-resultados-demonstracoes",
            "central-resultados-itr",
            "central-resultados-release",
            "central-resultados-resultados",
            "central-resultados-transcricao",
            "central-resultados-videos",
            "video-de-conferencia",
        ),
    ),
    "SAUD3": EquityMziqCompany(
        ticker="SAUD3",
        company_id="c504a4a5-75e7-4404-8af7-524b50cd7e11",
        category_internal_names=(
            "Bradsaude_central-apresentacao",
            "Bradsaude_central-relatorios-resultados",
            "bradsaude_interativa",
            "Bradsaude_central-itrdfp",
            "Bradsaude_central-webcast",
            "Bradsaude_central-replay",
            "Bradsaude_central-transcricao",
        ),
    ),
    "ALOS3": EquityMziqCompany(
        ticker="ALOS3",
        company_id="330c258b-6212-45ce-8c13-557ea46cc23a",
        category_internal_names=(
            "apresentacao-resultados",
            "demonstracoes-financeiras-anuais-completas",
            "demonstracoes-financeiras-itr-dfp",
            "release-resultados",
            "teleconferencia-resultados",
            "transcricao-teleconferencia",
        ),
    ),
    "VBBR3": EquityMziqCompany(
        ticker="VBBR3",
        company_id="d243bdaa-0468-4f64-8c09-ba0bcee9789b",
        category_internal_names=(
            "central-apresentacao-resultados",
            "central-itr/dfp",
            "central-planilhas-segmento",
            "central-planilhas-segmento-comerc",
            "central-resultados-financeiros",
            "central-teleconferencia-audio",
            "central-transcricao",
            "ra-demonstracoes-financeiras",
        ),
    ),
    "KLBN4": EquityMziqCompany(
        ticker="KLBN4",
        company_id="1c41fa99-efe7-4e72-81dd-5b571f5aa376",
        category_internal_names=(
            "central_de_resultados_apresentacao_de_resultados",
            "central_de_resultados_dados_excel",
            "central_de_resultados_demonstracoes_financeiras_itrdfp",
            "central_de_resultados_releases_de_resultados",
            "central_de_resultados_teleconferencia_de_resultados_audio",
            "central_de_resultados_transcricao",
            "video-de-resultados",
        ),
    ),
    "FESA4": EquityMziqCompany(
        ticker="FESA4",
        company_id="e71f73d4-4d0a-41fb-8e5b-8d7f3660b6ad",
        category_internal_names=(
            "resultados_trimestrais_apresentacao_resultados",
            "resultados_trimestrais_audio_webcast",
            "resultados_trimestrais_itr",
            "resultados_trimestrais_planilha_valuation",
            "resultados_trimestrais_press_release",
            "resultados_trimestrais_transcricao",
            "resultados_trimestrais_webcast",
        ),
    ),
    "LEVE3": EquityMziqCompany(
        ticker="LEVE3",
        company_id="6b90b8ef-4914-4021-8296-c5aca7b388eb",
        category_internal_names=(
            "apresentacao-central-resultados",
            "central-de-resultados-dfp-demonstracoes-financeiras-padronizadas",
            "central-de-resultados-itr-informacoes-trimestrais",
            "central-de-resultados-releases-de-resultados",
            "teleconferencia-audio-central-resultados",
        ),
    ),
    "PASS3": EquityMziqCompany(
        ticker="PASS3",
        company_id="17eafccb-2e4b-40d4-8da2-1ba38e6d4676",
        # One more category ("Vídeo de Resultados") was present in the
        # page's own JS array but with a mangled, non-slug internal_name
        # (an apparent encoding artifact) -- excluded rather than guessed
        # at its real slug; the 5 below are exactly what was live-verified.
        category_internal_names=(
            "releases",
            "DFs",
            "planilhas",
            "apresentacao-teleconferencia",
            "audios",
        ),
    ),
}


def company_for_ticker(ticker: str) -> EquityMziqCompany | None:
    return EQUITY_MZIQ_COMPANIES.get(ticker.strip().upper())


# Alias matching the fund_for_ticker/build_years_target/build_documents_target
# interface iip.cli.main._collect_mziq_manager_documents expects from any
# manager-specific MZIQ config module (see patria_mziq.py/btg_mziq.py) --
# "company" is the more accurate name for an equity issuer, but the shared
# CLI helper is generic across FII managers and equity issuers alike.
fund_for_ticker = company_for_ticker


def build_years_target(ticker: str):
    from .mziq import build_years_target as _build_years_target

    company = company_for_ticker(ticker)
    if company is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_years_target(company.company_id, company.category_internal_names)


def build_documents_target(ticker: str, year: int):
    from .mziq import build_documents_target as _build_documents_target

    company = company_for_ticker(ticker)
    if company is None:
        raise ValueError(f"no MZIQ config registered for ticker {ticker!r}")
    return _build_documents_target(
        company.company_id, year, company.category_internal_names
    )
