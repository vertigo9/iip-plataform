"""Source policy and provider matrix contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from iip.registry.models import AssetClass


class SourceRole(StrEnum):
    REGULATORY = "regulatory"
    INSTITUTIONAL_PRIMARY = "institutional_primary"
    MARKET_VALIDATION = "market_validation"
    ENRICHMENT = "enrichment"


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    roles: tuple[SourceRole, ...]
    asset_classes: tuple[AssetClass, ...]
    enabled: bool = True


@dataclass(frozen=True)
class SourcePolicy:
    asset_class: AssetClass
    providers: tuple[ProviderSpec, ...]
    priority: tuple[str, ...]


def default_provider_specs() -> tuple[ProviderSpec, ...]:
    fund = (AssetClass.FUND,)
    universal = tuple(AssetClass)
    return (
        ProviderSpec("cvm", (SourceRole.REGULATORY,), universal),
        ProviderSpec("fnet", (SourceRole.REGULATORY,), fund),
        ProviderSpec("b3", (SourceRole.MARKET_VALIDATION,), universal),
        ProviderSpec("xp_asset", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("patria", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("sparta", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("capitania", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("valora", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("btg", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("manati", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("trx", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("araujo_fontes", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("hedge", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("rio_bravo", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec("kinea", (SourceRole.INSTITUTIONAL_PRIMARY,), fund),
        ProviderSpec(
            "ri_company", (SourceRole.INSTITUTIONAL_PRIMARY,), (AssetClass.EQUITY,)
        ),
        ProviderSpec("sec", (SourceRole.REGULATORY,), (AssetClass.ADR,)),
        ProviderSpec(
            "issuer",
            (SourceRole.INSTITUTIONAL_PRIMARY,),
            (AssetClass.ETF, AssetClass.BDR, AssetClass.ADR),
        ),
        ProviderSpec("market_data", (SourceRole.ENRICHMENT,), universal),
    )


def default_priority_for(asset_class: AssetClass) -> tuple[str, ...]:
    if asset_class == AssetClass.FUND:
        return ("cvm", "fnet", "institutional", "b3", "market_data")
    if asset_class == AssetClass.EQUITY:
        return ("cvm", "ri_company", "b3", "market_data")
    if asset_class == AssetClass.ADR:
        return ("sec", "issuer", "b3", "market_data")
    if asset_class in (AssetClass.ETF, AssetClass.BDR):
        return ("issuer", "cvm", "b3", "market_data")
    return ("cvm", "b3", "market_data")


def build_default_policies() -> tuple[SourcePolicy, ...]:
    specs = default_provider_specs()
    return tuple(SourcePolicy(c, specs, default_priority_for(c)) for c in AssetClass)
