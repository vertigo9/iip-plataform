"""Simple deterministic anomaly detection over time-series observations."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev


@dataclass(frozen=True)
class AnomalyResult:
    anomalous: bool
    z_score: float
    baseline_mean: float
    baseline_std: float


def detect(
    values: tuple[float, ...], current: float, threshold: float = 3.0
) -> AnomalyResult:
    if not values:
        return AnomalyResult(False, 0.0, 0.0, 0.0)
    baseline = mean(values)
    deviation = pstdev(values)
    if deviation == 0:
        return AnomalyResult(current != baseline, 0.0, baseline, 0.0)
    z = (current - baseline) / deviation
    return AnomalyResult(abs(z) >= threshold, round(z, 12), baseline, deviation)
