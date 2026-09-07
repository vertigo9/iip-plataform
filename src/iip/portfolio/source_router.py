"""Bridge the real portfolio registry into the existing multi-provider router."""

from __future__ import annotations

from dataclasses import dataclass

from iip.portfolio.registry import PortfolioAsset
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
    def _asset_ref(asset: PortfolioAsset) -> AssetRef:
        source = None
        if asset.source_url:
            source_name = (asset.manager or "institutional").strip().lower()
            source = SourceRef(
                provider=source_name,
                role="institutional_primary",
                priority=3,
                url=asset.source_url,
                active=True,
            )

        sources = (source,) if source is not None else ()

        return AssetRef(
            ticker=asset.ticker,
            asset_class=asset.asset_class,
            asset_subtype=asset.subtype or "",
            segment=asset.segment or "",
            sources=sources,
        )

    def route(self, asset: PortfolioAsset) -> RoutedPortfolioAsset:
        asset_ref = self._asset_ref(asset)
        routes = self.router.routes_for(asset_ref)
        return RoutedPortfolioAsset(asset=asset, routes=routes)
