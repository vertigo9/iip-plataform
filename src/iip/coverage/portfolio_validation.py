"""Portfolio validation gates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    failures: tuple[str, ...]


def validate(
    *,
    identifiers_ok: bool,
    weights_ok: bool,
    evidence_ok: bool,
    decisions_ok: bool,
) -> ValidationResult:
    failures = []
    if not identifiers_ok:
        failures.append("identifiers")
    if not weights_ok:
        failures.append("weights")
    if not evidence_ok:
        failures.append("evidence")
    if not decisions_ok:
        failures.append("decisions")
    return ValidationResult(not failures, tuple(failures))
