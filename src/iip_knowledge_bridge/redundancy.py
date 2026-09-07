from collections import defaultdict

from .models import Exposure


def find_redundant_exposures(exposures: list[Exposure], threshold: float = 0.20):
    totals = defaultdict(float)
    contributors = defaultdict(list)
    for e in exposures:
        totals[e.factor] += e.weight
        contributors[e.factor].append(e.ticker)
    return [
        {"factor": f, "aggregate_weight": w, "assets": sorted(set(contributors[f]))}
        for f, w in sorted(totals.items(), key=lambda x: x[1], reverse=True)
        if w >= threshold
    ]
