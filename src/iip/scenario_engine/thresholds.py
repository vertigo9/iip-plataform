"""Decision confidence and scenario thresholds."""

from __future__ import annotations


def bounded(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def pass_rate(passed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return passed / total


def meets(value: float, threshold: float) -> bool:
    return float(value) >= float(threshold)
