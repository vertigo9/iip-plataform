"""Deep coverage regression report."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoverageReport:
    baseline_tests: int
    current_tests: int
    baseline_coverage: float
    current_coverage: float

    @property
    def regressions(self) -> tuple[str, ...]:
        failures = []
        if self.current_tests < self.baseline_tests:
            failures.append("test_count")
        if self.current_coverage < self.baseline_coverage:
            failures.append("coverage")
        return tuple(failures)

    @property
    def passed(self) -> bool:
        return not self.regressions
