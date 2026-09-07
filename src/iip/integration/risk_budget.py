"""Portfolio risk-budget primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskBudget:
    total: float
    used: float

    @property
    def available(self) -> float:
        return max(0.0, self.total - self.used)

    @property
    def utilization(self) -> float:
        return self.used / self.total if self.total > 0 else 1.0
