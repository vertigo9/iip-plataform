"""Batch provider implementations for institutional fund sources.

The batch introduces provider adapters only for providers with a defined,
testable source contract. It deliberately does not fabricate remote endpoints.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AdapterStatus(StrEnum):
    IMPLEMENTED = "implemented"
    MAPPED = "mapped"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ProviderAdapterSpec:
    provider: str
    manager: str
    status: AdapterStatus
    discover: Callable[..., Any] | None = None
    notes: str = ""


class InstitutionalProviderAdapter:
    """Small normalized adapter contract consumed by the provider runtime."""

    def __init__(self, spec: ProviderAdapterSpec) -> None:
        self.spec = spec

    @property
    def provider_name(self) -> str:
        return self.spec.provider

    def supports(self, asset: object) -> bool:
        manager = getattr(asset, "manager", None)
        return bool(manager and manager.casefold() == self.spec.manager.casefold())

    def discover(self, *args, **kwargs):
        if self.spec.discover is None:
            return ()
        return self.spec.discover(*args, **kwargs)


def build_batch_registry(
    discovery_functions: Mapping[str, Callable[..., Any]] | None = None,
) -> dict[str, InstitutionalProviderAdapter]:
    """Build normalized adapters without pretending mapped providers are ready."""
    funcs = dict(discovery_functions or {})
    managers = {
        "sparta": "Sparta",
        "btg": "BTG Pactual",
        "kinea": "Kinea",
        "hedge": "Hedge Investments",
        "rio_bravo": "Rio Bravo",
        "capitania": "Capitânia",
        "valora": "Valora",
        "manati": "Manati/ICM",
        "trx": "TRX",
        "araujo_fontes": "Araújo Fontes",
    }
    return {
        name: InstitutionalProviderAdapter(
            ProviderAdapterSpec(
                provider=name,
                manager=manager,
                status=(
                    AdapterStatus.IMPLEMENTED if name in funcs else AdapterStatus.MAPPED
                ),
                discover=funcs.get(name),
                notes=(
                    "Concrete adapter supplied by caller."
                    if name in funcs
                    else "Primary source must be validated before implementation."
                ),
            )
        )
        for name, manager in managers.items()
    }


def promoted_registry(
    discovery_functions: Mapping[str, Callable[..., Any]],
) -> dict[str, InstitutionalProviderAdapter]:
    """Return only adapters with an explicitly supplied implementation."""
    registry = build_batch_registry(discovery_functions)
    return {
        name: adapter
        for name, adapter in registry.items()
        if adapter.spec.status == AdapterStatus.IMPLEMENTED
    }
