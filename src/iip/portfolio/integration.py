"""Operational provider integration helpers.

D-OBSIDIAN-06.2-31 -> 06.2-40

This layer connects the operational provider manifests to the already tested
Source/Portfolio routing architecture without fabricating remote endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass

from iip.providers.factory import ProviderFactory
from iip.providers.registry import ProviderManifest, ProviderStatus


@dataclass(frozen=True)
class ProviderBinding:
    provider: ProviderManifest
    implementation_available: bool
    production_ready: bool


@dataclass(frozen=True)
class ProviderRoutingPlan:
    ticker: str
    bindings: tuple[ProviderBinding, ...]
    primary: ProviderBinding | None
    fallbacks: tuple[ProviderBinding, ...]


class OperationalProviderPlanner:
    """Create a production-safe provider plan for a portfolio asset."""

    def __init__(
        self,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self.factory = provider_factory or ProviderFactory()

    def binding(self, provider_name: str) -> ProviderBinding | None:
        manifest = self.factory.manifest(provider_name)
        if manifest is None:
            return None

        handle = self.factory.create(provider_name)
        implemented = bool(
            manifest.implementation and handle is not None and handle.provider
        )
        ready = implemented and manifest.status == ProviderStatus.READY
        return ProviderBinding(
            provider=manifest,
            implementation_available=implemented,
            production_ready=ready,
        )

    def plan_from_routes(
        self,
        ticker: str,
        provider_names: tuple[str, ...],
    ) -> ProviderRoutingPlan:
        bindings = tuple(
            binding
            for name in provider_names
            if (binding := self.binding(name)) is not None
        )
        ready = tuple(binding for binding in bindings if binding.production_ready)
        primary = ready[0] if ready else None
        fallbacks = ready[1:] if len(ready) > 1 else ()
        return ProviderRoutingPlan(
            ticker=ticker.upper(),
            bindings=bindings,
            primary=primary,
            fallbacks=fallbacks,
        )

    def implementation_gap(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                name
                for name, manifest in self.factory.manifests.items()
                if manifest.kind.value == "institutional"
                and manifest.status == ProviderStatus.PENDING
            )
        )
