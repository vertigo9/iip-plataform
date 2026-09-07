"""Provider runtime readiness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProbe:
    provider: str
    reachable: bool
    latency_ms: float
    error_rate: float


def ready(probe: RuntimeProbe) -> bool:
    return (
        probe.reachable
        and probe.latency_ms >= 0
        and 0.0 <= probe.error_rate <= 1.0
        and probe.error_rate < 0.05
    )
