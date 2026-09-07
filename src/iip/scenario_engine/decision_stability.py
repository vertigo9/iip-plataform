"""Decision stability analysis."""

from __future__ import annotations

from .models import DecisionScenario, StabilityResult


def assess(item: DecisionScenario, max_score_delta: float = 2.0) -> StabilityResult:
    delta = round(item.stressed_score - item.baseline_score, 12)
    changed = item.baseline_action.upper() != item.stressed_action.upper()
    stable = (not changed) and abs(delta) <= max_score_delta
    return StabilityResult(
        item.ticker.upper(),
        stable,
        changed,
        delta,
    )
