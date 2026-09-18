"""BTG Pactual's real-estate FII investor-relations documents via the
MZIQ platform (see ``iip.sources.mziq`` for the generic request/response
shapes) -- same lightweight, HTTP-only approach as
``iip.sources.patria_mziq``, applied to BTG Pactual's registry
positions.

Confirmed live (18/09/2026) for BTLG11 only. Unlike every Pátria fund
(whose ``company_id``/category config had to be found by capturing
real network requests via Playwright, see ``iip.sources.patria_mziq``'s
docstring), BTLG11's MZIQ config is plainly embedded in its own
static page HTML -- no browser needed even for discovery:
  - ``company_id`` sits in a literal
    ``var company_id = '<uuid>';`` assignment on
    https://btlg.btgpactual.com/resultados-e-documentos/central-de-downloads/
  - category internal names sit in a plain JS array of
    ``categories.push({title: ..., internal_name: ...})`` calls on the
    same page.

BTCI11 (BTG Pactual's other registry position) is on a DIFFERENT,
non-MZIQ platform (``btgpactual.com/asset-management/...``, an Astro
app) -- confirmed live: no MZIQ reference, no embedded API config
anywhere in its static HTML. Deliberately NOT included in
``BTG_MZIQ_FUNDS`` below; it would need its own network-capture
discovery pass (same method as the 4 non-static Pátria funds), not yet
done. Calling this module for BTCI11 raises, same as any other
unregistered ticker -- never silently guessed.

Same scope note as ``patria_mziq``: this is for DOCUMENT
retrieval (relatório gerencial, fatos relevantes, informes, etc.),
not NAV -- CVM's own structured data already covers BTLG11 (subtype
FII, verified CNPJ in the registry).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BtgMziqFund:
    ticker: str
    company_id: str
    category_internal_names: tuple[str, ...]


BTG_MZIQ_FUNDS: dict[str, BtgMziqFund] = {
    "BTLG11": BtgMziqFund(
        ticker="BTLG11",
        company_id="41be6346-c17f-47f5-88be-58b333a14261",
        category_internal_names=(
            "relatorios_gerenciais",
            "informes_mensal",
            "informes_anual_estruturado",
            "comunico_ao_mercado",
            "fato_relevante",
            "assembleia",
            "oferta_prospecto",
            "aviso_aos_cotistas",
            "aviso_aos_cotistas_estruturado",
            "laudo_avaliacao",
        ),
    ),
}


def fund_for_ticker(ticker: str) -> BtgMziqFund | None:
    return BTG_MZIQ_FUNDS.get(ticker.strip().upper())


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
