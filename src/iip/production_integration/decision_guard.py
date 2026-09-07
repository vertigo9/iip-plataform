"""Guardrails before exposing a portfolio decision."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionGuard:
    evidence_complete: bool
    provider_ready: bool
    reconciliation_ok: bool
    scenario_validated: bool

    @property
    def allowed(self) -> bool:
        return (
            self.evidence_complete
            and self.provider_ready
            and self.reconciliation_ok
            and self.scenario_validated
        )
