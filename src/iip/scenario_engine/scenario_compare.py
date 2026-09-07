"""Cross-scenario comparison."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioDelta:
    scenario_a: str
    scenario_b: str
    score_delta: float


def compare(
    a_name: str,
    a_score: float,
    b_name: str,
    b_score: float,
) -> ScenarioDelta:
    return ScenarioDelta(
        a_name,
        b_name,
        round(float(b_score) - float(a_score), 12),
    )
