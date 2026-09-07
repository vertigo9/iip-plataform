"""Portfolio-level exposure and concentration primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionExposure:
    ticker: str
    weight: float
    segment: str | None = None
    manager: str | None = None
    risk_profile: str | None = None


@dataclass(frozen=True)
class ConcentrationAlert:
    dimension: str
    value: str
    weight: float
    threshold: float


def concentration_alerts(
    positions: tuple[PositionExposure, ...],
    threshold: float = 0.20,
) -> tuple[ConcentrationAlert, ...]:
    grouped: dict[tuple[str, str], float] = {}
    for position in positions:
        for dimension, value in (
            ("manager", position.manager),
            ("segment", position.segment),
        ):
            if value:
                grouped[(dimension, value)] = (
                    grouped.get((dimension, value), 0.0) + position.weight
                )
    return tuple(
        ConcentrationAlert(d, v, w, threshold)
        for (d, v), w in grouped.items()
        if w > threshold
    )
