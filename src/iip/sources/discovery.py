"""Provider-aware discovery with deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass

from .registry import AssetRef
from .router import SourceRoute, SourceRouter


@dataclass(frozen=True)
class ProviderDiscovery:
    """Documents discovered through one source/provider route."""

    route: SourceRoute
    documents: tuple[object, ...]


class MultiProviderDiscovery:
    """Try active routes in priority order until a route succeeds.

    A provider returning an empty tuple is treated as a non-successful
    discovery and allows the next active route to be attempted. Exceptions
    are collected rather than hidden in the returned result.
    """

    def __init__(self, router: SourceRouter) -> None:
        self.router = router

    def discover(
        self,
        asset: AssetRef,
        years: range,
    ) -> tuple[ProviderDiscovery, ...]:
        results: list[ProviderDiscovery] = []

        for route in self.router.routes_for(asset):
            try:
                documents = tuple(route.provider.discover(asset, years))
            except Exception:  # noqa: S112,BLE001 — isola falha de uma rota de provider, tenta a proxima
                continue

            if documents:
                results.append(ProviderDiscovery(route=route, documents=documents))
                break

        return tuple(results)

    def discover_all(
        self,
        asset: AssetRef,
        years: range,
    ) -> tuple[ProviderDiscovery, ...]:
        """Discover from every active route that can return documents."""
        results: list[ProviderDiscovery] = []

        for route in self.router.routes_for(asset):
            try:
                documents = tuple(route.provider.discover(asset, years))
            except Exception:  # noqa: S112,BLE001 — isola falha de uma rota de provider, tenta a proxima
                continue

            if documents:
                results.append(ProviderDiscovery(route=route, documents=documents))

        return tuple(results)
