"""Health-aware source routing helpers."""

from __future__ import annotations

from dataclasses import dataclass

from iip.sources.health_registry import SourceHealthRegistry


@dataclass(frozen=True)
class ProviderHealthDecision:
    provider: str
    usable: bool
    reason: str


class HealthAwareProviderSelector:
    """Apply registered source health before production routing.

    Unknown providers are not declared healthy automatically; they are
    reported as ``unknown`` so a future production policy can decide.
    """

    def __init__(self, health_registry: SourceHealthRegistry) -> None:
        self.health_registry = health_registry

    def evaluate(self, provider_name: str) -> ProviderHealthDecision:
        health = self.health_registry.get(provider_name)
        if health is None:
            return ProviderHealthDecision(provider_name, False, "unknown")
        return ProviderHealthDecision(
            provider=provider_name,
            usable=health.healthy,
            reason="healthy" if health.healthy else "unhealthy",
        )
