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
        "sparta", ("fund",), AdapterKind.MAPPED,
        AdapterReadiness.MAPPED, None, "No validated transport adapter is registered.",
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
