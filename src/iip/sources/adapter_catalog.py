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
        "btg", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
    ),
    AdapterDescriptor(
        "kinea", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
    ),
    AdapterDescriptor(
        "capitania", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
    ),
    AdapterDescriptor(
        "valora", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
    ),
    AdapterDescriptor(
        "manati", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
    ),
    AdapterDescriptor(
        "trx", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
    ),
    AdapterDescriptor(
        "hedge", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
    ),
    AdapterDescriptor(
        "rio_bravo", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
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
