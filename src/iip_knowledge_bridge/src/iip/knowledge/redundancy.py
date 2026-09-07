from __future__ import annotations

from collections import defaultdict

from .models import Exposure


def find_redundant_exposures(
    exposures: list[Exposure], threshold: float = 0.20
) -> list[dict[str, object]]:
    totals: dict[str, float] = defaultdict(float)
    assets: dict[str, set[str]] = defaultdict(set)
    for e in exposures:
        totals[e.factor] += e.weight
        assets[e.factor].add(e.ticker)
    return [
        {
            "factor": factor,
            "aggregate_weight": round(weight, 6),
            "assets": sorted(assets[factor]),
        }
        for factor, weight in sorted(totals.items(), key=lambda x: x[1], reverse=True)
        if weight >= threshold
    ]
