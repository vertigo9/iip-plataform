"""Integrated service health state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceHealth:
    service: str
    healthy: bool
    latency_ms: float
    error_rate: float

    @property
    def degraded(self) -> bool:
        return not self.healthy or self.latency_ms > 1000 or self.error_rate >= 0.05
