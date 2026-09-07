"""Enterprise allocation control."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationControl:
    ticker: str
    target_weight: float
    maximum_weight: float
    current_weight: float
    approved: bool


def evaluate(
    ticker: str,
    target_weight: float,
    maximum_weight: float,
    current_weight: float,
) -> AllocationControl:
    target = max(0.0, min(1.0, target_weight))
    maximum = max(0.0, min(1.0, maximum_weight))
    current = max(0.0, min(1.0, current_weight))
    approved = target <= maximum and current >= 0.0
    return AllocationControl(ticker.upper(), target, maximum, current, approved)
