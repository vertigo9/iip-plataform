"""Deep health aggregation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthCheck:
    name: str
    healthy: bool
    severity: str = "normal"


@dataclass(frozen=True)
class HealthReport:
    checks: tuple[HealthCheck, ...]

    @property
    def healthy(self) -> bool:
        return bool(self.checks) and all(check.healthy for check in self.checks)

    @property
    def critical_failures(self) -> tuple[HealthCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if not check.healthy and check.severity == "critical"
        )
