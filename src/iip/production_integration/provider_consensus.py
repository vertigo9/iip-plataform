"""Consensus between independent provider observations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    provider: str
    value: float


@dataclass(frozen=True)
class Consensus:
    value: float
    providers: tuple[str, ...]
    spread: float


def calculate(
    observations: tuple[Observation, ...],
) -> Consensus:
    if not observations:
        return Consensus(0.0, (), 0.0)
    values = [item.value for item in observations]
    average = sum(values) / len(values)
    spread = max(values) - min(values)
    return Consensus(
        round(average, 12),
        tuple(item.provider for item in observations),
        round(spread, 12),
    )
