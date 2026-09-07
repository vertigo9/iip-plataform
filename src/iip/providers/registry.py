"""Operational provider manifest registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderKind(StrEnum):
    INSTITUTIONAL = "institutional"
    REGULATORY = "regulatory"
    MARKET = "market"
    ISSUER = "issuer"


class ProviderStatus(StrEnum):
    REGISTERED = "registered"
    READY = "ready"
    PARTIAL = "partial"
    PENDING = "pending"


@dataclass(frozen=True)
class ProviderManifest:
    name: str
    kind: ProviderKind
    status: ProviderStatus
    asset_classes: tuple[str, ...]
    source_roles: tuple[str, ...]
    implementation: str | None = None
    notes: str | None = None


FUND_MANAGERS = (
    "xp_asset",
    "patria",
    "sparta",
    "capitania",
    "valora",
    "btg",
    "manati",
    "trx",
    "araujo_fontes",
    "hedge",
    "rio_bravo",
    "kinea",
)

TRANSVERSAL_PROVIDERS = (
    "cvm",
    "fnet",
    "b3",
    "ri_company",
    "sec",
    "issuer",
    "market_data",
)


def default_provider_manifests() -> tuple[ProviderManifest, ...]:
    result = []
    for name in FUND_MANAGERS:
        result.append(
            ProviderManifest(
                name=name,
                kind=ProviderKind.INSTITUTIONAL,
                status=ProviderStatus.READY
                if name in {"xp_asset", "patria"}
                else ProviderStatus.PENDING,
                asset_classes=("fund",),
                source_roles=("institutional_primary",),
                implementation=(
                    "iip.sources.xp_asset.XPAssetProvider"
                    if name == "xp_asset"
                    else "iip.harvest.patria"
                    if name == "patria"
                    else None
                ),
            )
        )
    result.extend(
        [
            ProviderManifest(
                "cvm",
                ProviderKind.REGULATORY,
                ProviderStatus.REGISTERED,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("regulatory",),
            ),
            ProviderManifest(
                "fnet",
                ProviderKind.REGULATORY,
                ProviderStatus.REGISTERED,
                ("fund",),
                ("regulatory",),
            ),
            ProviderManifest(
                "b3",
                ProviderKind.MARKET,
                ProviderStatus.REGISTERED,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("market_validation",),
            ),
            ProviderManifest(
                "ri_company",
                ProviderKind.INSTITUTIONAL,
                ProviderStatus.PENDING,
                ("equity",),
                ("institutional_primary",),
            ),
            ProviderManifest(
                "sec",
                ProviderKind.REGULATORY,
                ProviderStatus.REGISTERED,
                ("adr",),
                ("regulatory",),
            ),
            ProviderManifest(
                "issuer",
                ProviderKind.ISSUER,
                ProviderStatus.PENDING,
                ("etf", "bdr", "adr"),
                ("institutional_primary",),
            ),
            ProviderManifest(
                "market_data",
                ProviderKind.MARKET,
                ProviderStatus.REGISTERED,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("enrichment",),
            ),
        ]
    )
    return tuple(result)


def manifest_map() -> dict[str, ProviderManifest]:
    return {item.name: item for item in default_provider_manifests()}
