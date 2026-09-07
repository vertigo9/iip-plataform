"""Decision validation gates."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Decision, Verdict


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reasons: tuple[str, ...] = ()


def validate_decision(decision: Decision) -> ValidationResult:
    reasons = []
    if not decision.evidence:
        reasons.append("missing_evidence")
    if decision.verdict == Verdict.COMPRAR and decision.confidence < 0.34:
        reasons.append("low_confidence_for_buy")
    if not 0.0 <= decision.score <= 10.0:
        reasons.append("score_out_of_range")
    return ValidationResult(not reasons, tuple(reasons))
