"""Provider factory with compatibility for existing implementations."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from inspect import isclass

from .registry import ProviderManifest, ProviderStatus, manifest_map


@dataclass(frozen=True)
class ProviderHandle:
    manifest: ProviderManifest
    provider: object | None


class ProviderFactory:
    def __init__(self, manifests=None) -> None:
        self.manifests = {
            item.name: item for item in (manifests or manifest_map().values())
        }

    def manifest(self, name: str) -> ProviderManifest | None:
        return self.manifests.get(name.strip().lower())

    @staticmethod
    def _instantiate_implementation(implementation: str) -> object:
        module_name, symbol_name = implementation.rsplit(".", 1)
        module = importlib.import_module(module_name)
        symbol = getattr(module, symbol_name)

        if isclass(symbol):
            return symbol()

        # Legacy Pátria integration is a module-level implementation, not a
        # provider class. Preserve it as the provider object.
        if (
            hasattr(symbol, "collect")
            or hasattr(symbol, "harvest")
            or hasattr(symbol, "discover")
        ):
            return symbol

        return symbol

    def create(self, name: str) -> ProviderHandle | None:
        manifest = self.manifest(name)
        if manifest is None:
            return None

        if manifest.status in {ProviderStatus.PENDING, ProviderStatus.PARTIAL}:
            return ProviderHandle(manifest, None)

        if not manifest.implementation:
            return ProviderHandle(manifest, None)

        return ProviderHandle(
            manifest,
            self._instantiate_implementation(manifest.implementation),
        )
