"""Production certification and migration readiness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Certification:
    tests_green: bool
    coverage: float
    compatibility: bool
    security: bool
    deterministic: bool
    migration_ready: bool

    @property
    def certified(self) -> bool:
        return (
            self.tests_green
            and self.coverage >= 0.90
            and self.compatibility
            and self.security
            and self.deterministic
            and self.migration_ready
        )
