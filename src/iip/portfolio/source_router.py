"""Bridge the real portfolio registry into the existing multi-provider router."""

from __future__ import annotations

from dataclasses import dataclass

from iip.portfolio.registry import PortfolioAsset
from iip.portfolio.source_policy import PortfolioSourcePolicyResolver
from iip.sources.registry import AssetRef, SourceRef
from iip.sources.router import SourceRoute, SourceRouter


@dataclass(frozen=True)
class RoutedPortfolioAsset:
    """A real portfolio asset plus its resolved source routes."""

    asset: PortfolioAsset
    routes: tuple[SourceRoute, ...]

    @property
    def primary(self) -> SourceRoute | None:
        return self.routes[0] if self.routes else None

    @property
    def fallbacks(self) -> tuple[SourceRoute, ...]:
        return self.routes[1:] if len(self.routes) > 1 else ()


class PortfolioSourceRouter:
    """Create SourceRef records from a portfolio asset and use SourceRouter.

    The existing SourceRouter remains the single routing implementation.
    This bridge only adapts PortfolioAsset -> AssetRef and therefore keeps the
    old Source Registry and Provider Registry contracts intact.
    """

    def __init__(self, router: SourceRouter) -> None:
        self.router = router

    @staticmethod
    def asset_ref(asset: PortfolioAsset) -> AssetRef:
        policy = PortfolioSourcePolicyResolver().resolve(asset.ticker)
        institutional = policy.institutional_provider if policy else None
        sources = []
        if asset.source_url and institutional is not None:
            sources.append(
                SourceRef(
                    provider=institutional.name,
                    role="institutional_primary",
                    priority=3,
                    url=asset.source_url,
                    active=True,
                )
            )

        if asset.asset_class.casefold() in {"equity", "etf", "bdr", "adr"}:
            sources.append(
                SourceRef(
                    provider="b3",
                    role="market_validation",
                    priority=4,
                    url=f"https://api.usebolsai.com/api/v1/fundamentals/{asset.ticker.upper()}",
                    active=True,
                )
            )
            sources.append(
                SourceRef(
                    provider="b3_brapi",
                    role="market_validation",
                    priority=5,
                    url=f"https://brapi.dev/api/quote/{asset.ticker.upper()}",
                    active=True,
                )
            )

        if asset.asset_class.casefold() == "fund" and asset.cnpj:
            sources.append(
                SourceRef(
                    provider="cvm",
                    role="regulatory",
                    priority=1,
                    url="https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS",
                    active=True,
                )
            )

        return AssetRef(
            ticker=asset.ticker,
            asset_class=asset.asset_class,
            asset_subtype=asset.subtype or "",
            segment=asset.segment or "",
            cnpj=asset.cnpj,
            sources=tuple(sources),
        )

    _asset_ref = asset_ref

    def route(self, asset: PortfolioAsset) -> RoutedPortfolioAsset:
        asset_ref = self.asset_ref(asset)
        routes = self.router.routes_for(asset_ref)
        return RoutedPortfolioAsset(asset=asset, routes=routes)
