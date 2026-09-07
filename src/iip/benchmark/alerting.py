"""Benchmark and system alert policies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdAlert:
    name: str
    severity: str
    observed: float
    threshold: float


def threshold_alert(
    name: str,
    observed: float,
    threshold: float,
    *,
    higher_is_worse: bool = True,
) -> ThresholdAlert | None:
    triggered = observed >= threshold if higher_is_worse else observed <= threshold
    if not triggered:
        return None
    severity = (
        "high"
        if (
            observed >= threshold * 1.5
            if higher_is_worse
            else observed <= threshold * 1.5
        )
        else "medium"
    )
    return ThresholdAlert(name, severity, observed, threshold)
