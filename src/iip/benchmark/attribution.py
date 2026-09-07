"""Performance attribution by explicit portfolio segments."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class AttributionItem:
    dimension: str
    value: str
    contribution: float


def attribute(
    observations: tuple[tuple[str, float, float], ...],
    dimension: str,
) -> tuple[AttributionItem, ...]:
    grouped = defaultdict(float)
    for value, weight, performance in observations:
        grouped[value] += weight * performance
    return tuple(
        AttributionItem(dimension, value, round(contribution, 12))
        for value, contribution in sorted(grouped.items())
    )
