"""Explicit readiness catalog for source adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AdapterKind(StrEnum):
    DOCUMENT = "document"
    METRIC = "metric"
    BULK = "bulk"
    LEGACY_FILE = "legacy_file"
    MAPPED = "mapped"


class AdapterReadiness(StrEnum):
    READY = "ready"
    CONFIGURATION_REQUIRED = "configuration_required"
    CONTRACT_REQUIRED = "contract_required"
    MAPPED = "mapped"


@dataclass(frozen=True)
class AdapterDescriptor:
    provider: str
    asset_classes: tuple[str, ...]
    kind: AdapterKind
    readiness: AdapterReadiness
    implementation: str | None
    reason: str


ADAPTER_CATALOG: tuple[AdapterDescriptor, ...] = (
    AdapterDescriptor(
        "xp_asset", ("fund",), AdapterKind.DOCUMENT,
        AdapterReadiness.READY, "XPAssetProvider", "XP Asset document discovery and HTTP transport.",
    ),
    AdapterDescriptor(
        "b3", ("equity", "etf", "bdr", "adr"), AdapterKind.DOCUMENT,
        AdapterReadiness.CONFIGURATION_REQUIRED,
        "BolsaiEquityProvider", "Requires IIP_BOLSAI_API_KEY.",
    ),
        AdapterDescriptor(
            "b3_brapi", ("equity", "etf", "bdr", "adr"), AdapterKind.DOCUMENT,
            AdapterReadiness.CONFIGURATION_REQUIRED,
            "BrapiMarketProvider", "Requires IIP_BRAPI_TOKEN.",
        ),
    AdapterDescriptor(
        "cvm", ("fund",), AdapterKind.BULK,
        AdapterReadiness.READY, "CvmFiiProvider",
        "Bulk annual ZIP is filtered by verified CNPJ before evidence is emitted.",
    ),
    AdapterDescriptor(
        "cvm_renda_fixa", ("fixed_income",), AdapterKind.METRIC,
        AdapterReadiness.CONTRACT_REQUIRED, "CvmRendaFixaHTTPHarvester",
        "Produces structured series/profile data, not one document per asset.",
    ),
    AdapterDescriptor(
        "patria", ("fund",), AdapterKind.LEGACY_FILE,
        AdapterReadiness.CONTRACT_REQUIRED, "iip.harvest.patria.harvest",
        "Legacy browser harvester writes files and needs an Atlas file adapter.",
    ),
    AdapterDescriptor(
        "patria_mziq", ("fund",), AdapterKind.DOCUMENT,
        AdapterReadiness.READY,
        "iip.sources.patria_mziq + iip.sources.mziq_harvester.MziqHTTPHarvester",
        "Lightweight HTTP-only alternative to 'patria' (no Playwright) -- "
        "confirmed live for all 5 Pátria funds (HGRU11, LVBI11, HGCR11, "
        "PVBI11, PCIP11) on 18/09/2026. Documents only (relatório de "
        "gestão, fatos relevantes, etc.), never NAV -- the monthly "
        "'informe_contabil_mensal' PDF was confirmed to be the same CVM "
        "Anexo 39-I filing 'cvm' already covers from structured CSV.",
    ),
    AdapterDescriptor(
        "sparta", ("fund",), AdapterKind.METRIC,
        AdapterReadiness.READY,
        "iip.sources.sparta_reports + iip.sources.sparta_reports_harvester.SpartaReportsHTTPHarvester",
        "PDF-parsed cota patrimonial (NAV per quota), wired to `iip "
        "collect-sparta-history` (see "
        "iip.portfolio.historical_series.collect_sparta_report_history). "
        "Built for CRAA11, whose CNPJ is confirmed absent from CVM's own "
        "FIAGRO dataset. Confirmed READY for CRAA11 only -- ran live "
        "(18/09/2026) against JURO11/CDII11 (Sparta's other 2 funds) and "
        "their PDF report uses a different layout with no matching NAV "
        "grid at all (see iip.sources.sparta_reports module docstring); "
        "pending, not a blocker since CVM's Informe Diário already covers "
        "those two.",
    ),
    AdapterDescriptor(
        "btg_mziq", ("fund",), AdapterKind.DOCUMENT,
        AdapterReadiness.READY,
        "iip.sources.btg_mziq + iip.sources.mziq_harvester.MziqHTTPHarvester",
        "Lightweight HTTP-only MZIQ document provider, confirmed live "
        "(18/09/2026) for BTLG11 only -- its company_id/category config "
        "is plainly embedded in its own static page HTML, no Playwright "
        "needed even for discovery. BTCI11 (BTG's other registry "
        "position) is on a different, non-MZIQ platform (Astro app) -- "
        "not investigated, calling this module for it raises rather "
        "than guessing.",
    ),
    AdapterDescriptor(
        "solutions_ir", ("fund",), AdapterKind.DOCUMENT,
        AdapterReadiness.READY,
        "iip.sources.solutions_ir + "
        "iip.sources.solutions_ir_harvester.SolutionsIrHTTPHarvester",
        "Closes out the BTCI11 gap ('btg' below). Its own IR page "
        "(an Astro app, no MZIQ) actively blocked a Playwright headless "
        "browser (net::ERR_HTTP2_PROTOCOL_ERROR, then a hard timeout "
        "with HTTP/2 disabled) -- confirmed live (18/09/2026) via a "
        "different method instead: the page's static HTML embeds an "
        "astro-island with apiBaseUrl/siteId in its props attribute "
        "(no execution needed), and its referenced JS component bundle "
        "(fetched, never run) had apiFundId/apiFundCnpj as literal "
        "default parameter values; the real endpoint path "
        "(/v2/asset/{fund_id}/documents/{cnpj}) came from grep'ing the "
        "larger vendor JS bundle for a template literal built from "
        "this.apiBaseUrl. One plain GET returns all 803 real BTCI11 "
        "documents, no pagination. Same platform (per this session's "
        "equity_mziq.py investigation) as CSUD3's post-2024 IR site, "
        "not yet registered here.",
    ),
    AdapterDescriptor(
        "btg", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "BTCI11 is now covered by 'solutions_ir' above; BTLG11 by "
        "'btg_mziq'. This entry itself still has no validated transport "
        "adapter of its own -- kept as a placeholder pointing to both.",
    ),
    AdapterDescriptor(
        "static_pdf_listing", ("fund",), AdapterKind.DOCUMENT,
        AdapterReadiness.READY,
        "iip.sources.static_pdf_listing + "
        "iip.sources.static_pdf_listing_harvester.StaticPdfListingHTTPHarvester",
        "Lightweight HTTP-only document provider covering the 7 managers "
        "below (Kinea, Capitânia, Valora, Manati, TRX, Hedge, Rio Bravo) "
        "-- confirmed live (18/09/2026) that every one of them lists its "
        "reports as plain <a href=\"*.pdf\"> links directly in static "
        "HTML (mostly WordPress uploads), simpler than even the MZIQ "
        "platform: no API, no company_id, just a GET on the fund's own "
        "documents page. KNRI11 and RBVA11's registry source_url values "
        "were confirmed dead (404 live); working URLs were found via web "
        "search and are registered in the module, not the registry.",
    ),
    AdapterDescriptor(
        "kinea", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "See 'static_pdf_listing' -- KNRI11 is covered there.",
    ),
    AdapterDescriptor(
        "capitania", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "See 'static_pdf_listing' -- CPTI11 is covered there.",
    ),
    AdapterDescriptor(
        "valora", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "See 'static_pdf_listing' -- VGIP11 is covered there.",
    ),
    AdapterDescriptor(
        "manati", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "See 'static_pdf_listing' -- MANA11 is covered there.",
    ),
    AdapterDescriptor(
        "trx", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "See 'static_pdf_listing' -- TRXF11 is covered there.",
    ),
    AdapterDescriptor(
        "hedge", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "See 'static_pdf_listing' -- HGBS11 is covered there.",
    ),
    AdapterDescriptor(
        "rio_bravo", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None,
        "See 'static_pdf_listing' -- RBVA11 is covered there.",
    ),
)


def adapter_descriptor(provider: str) -> AdapterDescriptor | None:
    name = provider.strip().casefold()
    return next((item for item in ADAPTER_CATALOG if item.provider == name), None)


def ready_adapters() -> tuple[AdapterDescriptor, ...]:
    return tuple(
        item for item in ADAPTER_CATALOG
        if item.readiness in {
            AdapterReadiness.READY,
            AdapterReadiness.CONFIGURATION_REQUIRED,
        }
    )
