"""Enterprise provider coverage matrix."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCoverage:
    provider: str
    supported_domains: tuple[str, ...]
    healthy: bool
    priority: int


def matrix(
    providers: tuple[ProviderCoverage, ...],
) -> tuple[ProviderCoverage, ...]:
    return tuple(
        sorted(
            providers,
            key=lambda item: (not item.healthy, item.priority, item.provider),
        )
    )


def domain_coverage(
    providers: tuple[ProviderCoverage, ...],
) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for provider in providers:
        if not provider.healthy:
            continue
        for domain in provider.supported_domains:
            counts[domain] = counts.get(domain, 0) + 1
    return tuple(sorted(counts.items()))
