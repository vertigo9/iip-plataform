"""Adaptive source priority."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePriority:
    provider: str
    reliability: float
    freshness: float
    priority: float


def rank(provider: str, reliability: float, freshness: float) -> SourcePriority:
    reliability = max(0.0, min(1.0, reliability))
    freshness = max(0.0, min(1.0, freshness))
    return SourcePriority(
        provider=provider,
        reliability=reliability,
        freshness=freshness,
        priority=round(0.7 * reliability + 0.3 * freshness, 12),
    )
