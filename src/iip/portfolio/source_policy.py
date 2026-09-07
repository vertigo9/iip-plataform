"""Bind real portfolio assets to source policies without mutating old registries."""

from __future__ import annotations

from dataclasses import dataclass

from iip.portfolio.registry import PORTFOLIO_ASSETS, PortfolioAsset
from iip.sources.policy import (
    ProviderSpec,
    SourcePolicy,
    default_priority_for,
    default_provider_specs,
)


@dataclass(frozen=True)
class AssetSourcePolicy:
    asset: PortfolioAsset
    policy: SourcePolicy
    institutional_provider: ProviderSpec | None


class PortfolioSourcePolicyResolver:
    """Resolve a portfolio asset into its transversal and institutional sources."""

    def __init__(
        self,
        assets: tuple[PortfolioAsset, ...] = PORTFOLIO_ASSETS,
        providers: tuple[ProviderSpec, ...] | None = None,
    ) -> None:
        self.assets = assets
        self.providers = providers or default_provider_specs()
        self._providers = {provider.name: provider for provider in self.providers}

    def resolve(self, ticker: str) -> AssetSourcePolicy | None:
        target = ticker.strip().upper()
        asset = next((item for item in self.assets if item.ticker == target), None)
        if asset is None:
            return None

        asset_class = self._map_asset_class(asset.asset_class)
        priority = default_priority_for(asset_class)

        eligible = tuple(
            provider
            for provider in self.providers
            if asset_class in provider.asset_classes and provider.enabled
        )

        institutional = self._institutional_provider(asset, eligible)

        # Keep canonical cross-asset providers plus the specific institutional
        # provider. The priority tuple remains the IIP high-level policy.
        selected_names = {provider.name for provider in eligible}
        if institutional is not None:
            selected_names.add(institutional.name)

        selected = tuple(
            provider
            for provider in self.providers
            if provider.name in selected_names and provider.enabled
        )

        policy = SourcePolicy(
            asset_class=asset_class,
            providers=selected,
            priority=priority,
        )
        return AssetSourcePolicy(
            asset=asset,
            policy=policy,
            institutional_provider=institutional,
        )

    @staticmethod
    def _map_asset_class(asset_class: str):
        from iip.registry.models import AssetClass

        mapping = {
            "fund": AssetClass.FUND,
            "equity": AssetClass.EQUITY,
            "etf": AssetClass.ETF,
            "bdr": AssetClass.BDR,
            "adr": AssetClass.ADR,
            "fixed_income": AssetClass.FIXED_INCOME,
        }
        return mapping.get(asset_class, AssetClass.OTHER)

    def _institutional_provider(
        self,
        asset: PortfolioAsset,
        eligible: tuple[ProviderSpec, ...],
    ) -> ProviderSpec | None:
        manager = (asset.manager or "").lower()

        aliases = {
            "xp asset": "xp_asset",
            "pátria": "patria",
            "patria": "patria",
            "sparta": "sparta",
            "capitânia": "capitania",
            "capitania": "capitania",
            "valora": "valora",
            "btg pactual": "btg",
            "manati/icm": "manati",
            "trx": "trx",
            "araujo fontes": "araujo_fontes",
            "araújo fontes": "araujo_fontes",
            "hedge investments": "hedge",
            "rio bravo": "rio_bravo",
            "kinea": "kinea",
        }

        provider_name = aliases.get(manager)
        if provider_name is None:
            return None

        provider = self._providers.get(provider_name)
        return provider if provider in eligible else None

    def resolve_many(
        self,
        tickers: tuple[str, ...] | None = None,
    ) -> tuple[AssetSourcePolicy, ...]:
        targets = (
            {ticker.strip().upper() for ticker in tickers}
            if tickers is not None
            else None
        )
        results = []
        for asset in self.assets:
            if targets is not None and asset.ticker not in targets:
                continue
            resolved = self.resolve(asset.ticker)
            if resolved is not None:
                results.append(resolved)
        return tuple(results)
