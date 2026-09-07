"""Registry for document providers."""

from __future__ import annotations

from .health_registry import SourceHealthRegistry
from .provider import DocumentProvider
from .registry import AssetRef


class ProviderRegistry:
    """Resolve a document provider for an asset."""

    def __init__(self) -> None:
        self._providers: dict[str, DocumentProvider] = {}

    def register(self, provider: DocumentProvider) -> None:
        name = provider.provider_name.strip().lower()

        if not name:
            raise ValueError("provider_name must not be empty")

        if name in self._providers:
            raise ValueError(f"Provider already registered: {name}")

        self._providers[name] = provider

    def get(self, provider_name: str) -> DocumentProvider | None:
        return self._providers.get(provider_name.strip().lower())

    def resolve(self, asset: AssetRef) -> DocumentProvider | None:
        """Return the first registered provider supporting the asset."""
        for provider in self._providers.values():
            if provider.supports(asset):
                return provider

        return None

    def resolve_healthy(
        self,
        asset: AssetRef,
        health_registry: SourceHealthRegistry,
    ) -> DocumentProvider | None:
        """Return the first supporting provider that is enabled and available.

        Providers without a health record are not considered healthy. The
        legacy :meth:`resolve` method intentionally remains unchanged.
        """
        for provider in self._providers.values():
            if not provider.supports(asset):
                continue

            health = health_registry.get(provider.provider_name)
            if health is None:
                continue

            if health.enabled and health.available:
                return provider

        return None

    def clear(self) -> None:
        self._providers.clear()
