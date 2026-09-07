"""Score calibration helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .models import HistoricalDecision


@dataclass(frozen=True)
class CalibrationBin:
    minimum_score: float
    maximum_score: float
    observations: int
    positive_rate: float


def calibrate(
    decisions: tuple[HistoricalDecision, ...],
    bins: tuple[tuple[float, float], ...] = (
        (0.0, 4.0),
        (4.0, 6.0),
        (6.0, 8.0),
        (8.0, 10.0),
    ),
) -> tuple[CalibrationBin, ...]:
    output = []
    for minimum, maximum in bins:
        selected = [
            d
            for d in decisions
            if minimum <= d.score < maximum and d.realized_return is not None
        ]
        positive = sum(d.realized_return >= 0 for d in selected)
        output.append(
            CalibrationBin(
                minimum,
                maximum,
                len(selected),
                positive / len(selected) if selected else 0.0,
            )
        )
    return tuple(output)
