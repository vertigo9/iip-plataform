"""Regression guard contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegressionBaseline:
    tests: int
    coverage: float
    required_modules: tuple[str, ...]


@dataclass(frozen=True)
class RegressionCurrent:
    tests: int
    coverage: float
    modules: tuple[str, ...]


def compare(
    baseline: RegressionBaseline, current: RegressionCurrent
) -> tuple[bool, tuple[str, ...]]:
    issues = []
    if current.tests < baseline.tests:
        issues.append("test_count_decreased")
    if current.coverage < baseline.coverage:
        issues.append("coverage_decreased")
    for module in baseline.required_modules:
        if module not in current.modules:
            issues.append(f"missing_module:{module}")
    return (not issues, tuple(issues))
