"""Production readiness gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Readiness:
    tests_green: bool
    coverage: float
    audit_ready: bool
    recovery_ready: bool

    @property
    def ready(self) -> bool:
        return (
            self.tests_green
            and self.coverage >= 0.90
            and self.audit_ready
            and self.recovery_ready
        )
