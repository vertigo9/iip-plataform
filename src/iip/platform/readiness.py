"""Platform readiness gate for transitioning from development to production."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessGate:
    full_suite_green: bool
    providers_certified: int
    real_e2e_validated: int
    source_policies_present: bool
    legacy_contracts_preserved: bool

    @property
    def production_ready(self) -> bool:
        return all(
            (
                self.full_suite_green,
                self.providers_certified > 0,
                self.real_e2e_validated > 0,
                self.source_policies_present,
                self.legacy_contracts_preserved,
            )
        )
