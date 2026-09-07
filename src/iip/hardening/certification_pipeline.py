"""Full hardening certification pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .release import Certification


@dataclass(frozen=True)
class CertificationInput:
    tests_green: bool
    coverage: float
    compatibility: bool
    security: bool
    deterministic: bool
    migration_ready: bool


def certify(data: CertificationInput) -> Certification:
    return Certification(
        tests_green=data.tests_green,
        coverage=float(data.coverage),
        compatibility=data.compatibility,
        security=data.security,
        deterministic=data.deterministic,
        migration_ready=data.migration_ready,
    )
