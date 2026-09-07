"""Production release gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseGate:
    suite_green: bool
    coverage_percent: float
    audit_enabled: bool
    recovery_defined: bool
    live_execution_explicitly_enabled: bool

    @property
    def pass_gate(self) -> bool:
        return all(
            (
                self.suite_green,
                self.coverage_percent >= 80.0,
                self.audit_enabled,
                self.recovery_defined,
                self.live_execution_explicitly_enabled,
            )
        )
