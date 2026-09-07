"""Enterprise readiness assessment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseReadiness:
    full_suite_green: bool
    coverage: float
    source_controls: bool
    decision_validation: bool
    audit: bool
    recovery: bool
    reporting: bool

    @property
    def ready(self) -> bool:
        return all(
            (
                self.full_suite_green,
                self.coverage >= 80.0,
                self.source_controls,
                self.decision_validation,
                self.audit,
                self.recovery,
                self.reporting,
            )
        )
