"""Operational provider planning."""

from __future__ import annotations

from dataclasses import dataclass

from .factory import ProviderFactory
from .registry import FUND_MANAGERS, ProviderManifest, ProviderStatus


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
    def __init__(self, provider_factory: ProviderFactory | None = None) -> None:
        self.factory = provider_factory or ProviderFactory()

    def binding(self, provider_name: str) -> ProviderBinding | None:
        manifest = self.factory.manifest(provider_name)
        if manifest is None:
            return None

        try:
            handle = self.factory.create(provider_name)
        # isola falha de criacao do provider, trata como indisponivel
        except Exception:  # noqa: BLE001
            handle = None

        implemented = bool(handle is not None and handle.provider is not None)

        # Positional construction preserves compatibility with the public
        # ProviderBinding field name ``provider`` used by earlier tests/code.
        return ProviderBinding(
            manifest,
            implemented,
            implemented and manifest.status == ProviderStatus.READY,
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

        return ProviderRoutingPlan(
            ticker=ticker.upper(),
            bindings=bindings,
            primary=ready[0] if ready else None,
            fallbacks=ready[1:] if len(ready) > 1 else (),
        )

    def implementation_gap(self) -> tuple[str, ...]:
        # The roadmap gap concerns the 12 fund-manager providers only.
        # Transversal institutional providers such as RI Company are tracked
        # separately and must not inflate the fund-manager gap.
        return tuple(
            sorted(name for name in FUND_MANAGERS if not self._implemented(name))
        )

    def _implemented(self, name: str) -> bool:
        manifest = self.factory.manifest(name)
        if manifest is None or not manifest.implementation:
            return False

        try:
            handle = self.factory.create(name)
        # isola falha de criacao do provider, trata como indisponivel
        except Exception:  # noqa: BLE001
            return False

        return bool(handle is not None and handle.provider is not None)
