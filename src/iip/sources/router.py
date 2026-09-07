"""Multi-provider source routing for IIP.

D-OBSIDIAN-06.2-09
"""

from __future__ import annotations

from dataclasses import dataclass

from .provider import DocumentProvider
from .provider_registry import ProviderRegistry
from .registry import AssetRef, SourceRef, SourceRegistry


@dataclass(frozen=True)
class SourceRoute:
    """A resolved, active source/provider pair."""

    source: SourceRef
    provider: DocumentProvider


class SourceRouter:
    """Resolve active asset sources against the registered providers.

    Sources are considered in ascending priority order. Inactive sources are
    skipped. An explicit provider name is preferred, but the registry can
    still resolve a provider by asset capability when the named provider is
    not registered.
    """

    def __init__(
        self,
        *,
        source_registry: SourceRegistry,
        provider_registry: ProviderRegistry,
    ) -> None:
        self.source_registry = source_registry
        self.provider_registry = provider_registry

    def routes_for(self, asset: AssetRef) -> tuple[SourceRoute, ...]:
        routes: list[SourceRoute] = []

        for source in sorted(
            (item for item in asset.sources if item.active),
            key=lambda item: item.priority,
        ):
            provider = self.provider_registry.get(source.provider)
            if provider is None:
                provider = self.provider_registry.resolve(asset)

            if provider is None:
                continue

            routes.append(SourceRoute(source=source, provider=provider))

        return tuple(routes)

    def primary_route(self, asset: AssetRef) -> SourceRoute | None:
        routes = self.routes_for(asset)
        return routes[0] if routes else None

    def fallback_routes(self, asset: AssetRef) -> tuple[SourceRoute, ...]:
        routes = self.routes_for(asset)
        return routes[1:] if len(routes) > 1 else ()
