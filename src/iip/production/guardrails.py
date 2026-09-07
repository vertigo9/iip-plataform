"""Production guardrails for automated portfolio actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GuardrailDecision(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True)
class AutomationContext:
    source_certified: bool
    evidence_count: int
    decision_valid: bool
    simulated: bool = True


@dataclass(frozen=True)
class GuardrailResult:
    decision: GuardrailDecision
    reasons: tuple[str, ...]


def evaluate(ctx: AutomationContext) -> GuardrailResult:
    reasons = []
    if not ctx.source_certified:
        return GuardrailResult(GuardrailDecision.DENY, ("source_not_certified",))
    if ctx.evidence_count <= 0:
        reasons.append("missing_evidence")
    if not ctx.decision_valid:
        reasons.append("decision_invalid")
    if reasons:
        return GuardrailResult(GuardrailDecision.REVIEW, tuple(reasons))
    if ctx.simulated:
        return GuardrailResult(GuardrailDecision.REVIEW, ("simulation_only",))
    return GuardrailResult(GuardrailDecision.ALLOW, ())
