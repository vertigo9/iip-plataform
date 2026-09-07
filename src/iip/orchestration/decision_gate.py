"""Decision gate joining score, evidence, risk and thesis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionGateInput:
    score: float
    confidence: float
    evidence_count: int
    risk_level: str
    thesis_state: str


@dataclass(frozen=True)
class DecisionGateResult:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate(input_data: DecisionGateInput) -> DecisionGateResult:
    reasons = []
    if input_data.evidence_count <= 0:
        reasons.append("missing_evidence")
    if input_data.confidence < 0.50:
        reasons.append("low_confidence")
    if input_data.score < 5.0:
        reasons.append("score_below_floor")
    if input_data.thesis_state == "Mudança de tese":
        reasons.append("thesis_change_review")
    if input_data.risk_level == "Alto":
        reasons.append("high_risk_review")

    blocking = {"missing_evidence", "low_confidence", "score_below_floor"}
    return DecisionGateResult(
        allowed=not any(reason in blocking for reason in reasons),
        reasons=tuple(reasons),
    )
