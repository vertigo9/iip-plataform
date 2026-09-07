"""Decision hit-rate measurement."""

from __future__ import annotations

from .models import HistoricalDecision

POSITIVE_ACTIONS = {"APORTAR", "COMPRAR", "MANTER"}


def hit_rate(decisions: tuple[HistoricalDecision, ...]) -> float:
    evaluated = [
        d
        for d in decisions
        if d.realized_return is not None and d.action.upper() in POSITIVE_ACTIONS
    ]
    if not evaluated:
        return 0.0
    hits = sum(d.realized_return >= 0 for d in evaluated)
    return hits / len(evaluated)


def regime_hit_rate(
    decisions: tuple[HistoricalDecision, ...],
    regime,
) -> float:
    selected = tuple(d for d in decisions if d.regime == regime)
    return hit_rate(selected)
