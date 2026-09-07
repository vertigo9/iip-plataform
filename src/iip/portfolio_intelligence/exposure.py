"""Exposure aggregation across portfolio dimensions."""

from __future__ import annotations

from collections import defaultdict


def aggregate(
    holdings,
    dimension: str,
) -> tuple[tuple[str, float], ...]:
    grouped = defaultdict(float)
    for holding in holdings:
        value = getattr(holding, dimension, None)
        if value:
            grouped[str(value)] += holding.weight
    return tuple(
        (value, round(weight, 12)) for value, weight in sorted(grouped.items())
    )
