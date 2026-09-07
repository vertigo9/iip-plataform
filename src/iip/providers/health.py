"""Operational provider health service."""

from __future__ import annotations

from dataclasses import dataclass

from .operations import ProviderOperations


@dataclass(frozen=True)
class OperationalHealth:
    provider: str
    healthy: bool
    reason: str


class ProviderHealthService:
    def __init__(self, operations: ProviderOperations | None = None) -> None:
        self.operations = operations or ProviderOperations()

    def check(self, provider: str) -> OperationalHealth:
        diagnostic = self.operations.diagnostic(provider)
        if diagnostic is None:
            return OperationalHealth(provider, False, "unknown_provider")
        if diagnostic.usable_for_production:
            return OperationalHealth(provider, True, "ready")
        if diagnostic.implemented:
            return OperationalHealth(provider, False, "implementation_not_ready")
        return OperationalHealth(provider, False, "provider_not_implemented")
