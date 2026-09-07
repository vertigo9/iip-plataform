"""Enterprise release gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseGate:
    tests_green: bool
    coverage: float
    consolidation_ok: bool
    governance_ok: bool
    audit_ok: bool

    @property
    def certified(self) -> bool:
        return (
            self.tests_green
            and self.coverage >= 0.90
            and self.consolidation_ok
            and self.governance_ok
            and self.audit_ok
        )
