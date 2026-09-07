"""Production integration release certificate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseCertificate:
    tests_green: bool
    coverage: float
    provider_mesh_ok: bool
    evidence_ok: bool
    decision_guarded: bool
    reconciliation_ok: bool

    @property
    def certified(self) -> bool:
        return (
            self.tests_green
            and self.coverage >= 0.90
            and self.provider_mesh_ok
            and self.evidence_ok
            and self.decision_guarded
            and self.reconciliation_ok
        )
