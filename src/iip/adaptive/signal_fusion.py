"""Fusion of explicit intelligence signals."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    name: str
    value: float
    weight: float


@dataclass(frozen=True)
class FusedSignal:
    score: float
    contributors: tuple[str, ...]


def fuse(signals: tuple[Signal, ...]) -> FusedSignal:
    positive = [signal for signal in signals if signal.weight > 0]
    if not positive:
        return FusedSignal(0.0, ())
    total_weight = sum(signal.weight for signal in positive)
    score = sum(signal.value * signal.weight for signal in positive) / total_weight
    return FusedSignal(
        round(max(0.0, min(10.0, score)), 12),
        tuple(signal.name for signal in positive),
    )
