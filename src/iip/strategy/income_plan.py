"""Income planning contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncomePlan:
    current_annual_income: float
    target_annual_income: float
    gap: float
    coverage_ratio: float


def build(current_income: float, target_income: float) -> IncomePlan:
    current = max(0.0, float(current_income))
    target = max(0.0, float(target_income))
    gap = max(0.0, target - current)

    # Keep the native IEEE-754 division result. Tests and downstream
    # consumers may rely on exact arithmetic identity (e.g. 24000/36000 == 2/3).
    ratio = current / target if target > 0 else 1.0

    return IncomePlan(
        current,
        target,
        gap,
        ratio,
    )
