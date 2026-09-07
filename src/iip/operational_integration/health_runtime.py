"""Unified runtime health aggregation for providers and portfolio."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthComponent:
    name: str
    healthy: bool
    latency_ms: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class HealthSummary:
    components: tuple[HealthComponent, ...]

    @property
    def healthy(self) -> bool:
        return bool(self.components) and all(item.healthy for item in self.components)

    @property
    def degraded(self) -> bool:
        return any(not item.healthy for item in self.components)

    @property
    def average_latency_ms(self) -> float:
        values = [
            item.latency_ms for item in self.components if item.latency_ms is not None
        ]
        return sum(values) / len(values) if values else 0.0
