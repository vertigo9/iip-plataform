"""Provider operational diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from .factory import ProviderFactory


@dataclass(frozen=True)
class ProviderDiagnostic:
    name: str
    status: object
    implemented: bool
    usable_for_production: bool
    implementation: str | None


class ProviderOperations:
    def __init__(self, factory: ProviderFactory | None = None) -> None:
        self.factory = factory or ProviderFactory()

    def diagnostic(self, name: str) -> ProviderDiagnostic | None:
        manifest = self.factory.manifest(name)
        if manifest is None:
            return None
        handle = self.factory.create(name)
        implemented = bool(manifest.implementation and handle and handle.provider)
        return ProviderDiagnostic(
            manifest.name,
            manifest.status,
            implemented,
            bool(implemented and manifest.status.value == "ready"),
            manifest.implementation,
        )

    def diagnostics(self):
        return tuple(
            sorted(
                (self.diagnostic(name) for name in self.factory.manifests),
                key=lambda item: item.name,
            )
        )
