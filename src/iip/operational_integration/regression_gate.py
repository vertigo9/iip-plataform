"""Regression gate dedicated to operational integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegressionGate:
    baseline_tests: int
    current_tests: int
    baseline_coverage: float
    current_coverage: float

    @property
    def pass_gate(self) -> bool:
        return (
            self.current_tests >= self.baseline_tests
            and self.current_coverage >= self.baseline_coverage
        )
