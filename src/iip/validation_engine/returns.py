"""Return calculations with deterministic numeric normalization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReturnPoint:
    date: str
    value: float


def simple_return(start: float, end: float) -> float:
    if start <= 0:
        raise ValueError("start must be positive")
    return round((end / start) - 1.0, 12)


def cumulative_return(points: tuple[ReturnPoint, ...]) -> float:
    if len(points) < 2:
        return 0.0
    return simple_return(points[0].value, points[-1].value)


def max_drawdown(points: tuple[ReturnPoint, ...]) -> float:
    if not points:
        return 0.0
    peak = points[0].value
    worst = 0.0
    for point in points:
        peak = max(peak, point.value)
        if peak > 0:
            worst = min(worst, (point.value / peak) - 1.0)
    return round(abs(worst), 12)
