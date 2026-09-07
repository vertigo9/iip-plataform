"""Scenario-aware decision validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationGate:
    stable: bool
    evidence_complete: bool
    risk_acceptable: bool
    passed: bool


def evaluate(
    *,
    stable: bool,
    evidence_complete: bool,
    risk_acceptable: bool,
) -> ValidationGate:
    return ValidationGate(
        stable,
        evidence_complete,
        risk_acceptable,
        bool(stable and evidence_complete and risk_acceptable),
    )
