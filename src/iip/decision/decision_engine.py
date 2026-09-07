"""Decision engine: evidence -> score -> verdict."""

from __future__ import annotations

from .models import Decision, IntelligenceInput, Verdict
from .scoring import composite_score, confidence_score


def verdict_for(item: IntelligenceInput, score: float) -> Verdict:
    thesis = item.thesis_signal.casefold()

    if thesis == "mudança de tese":
        return Verdict.REDUZIR if score < 7 else Verdict.AGUARDAR

    if score >= 8.5:
        return Verdict.COMPRAR
    if score >= 7.0:
        return Verdict.MANTER
    if score >= 5.0:
        return Verdict.AGUARDAR
    if score >= 3.5:
        return Verdict.REDUZIR
    return Verdict.VENDER


def decide(item: IntelligenceInput) -> Decision:
    score = composite_score(item)
    confidence = confidence_score(item)
    reasons = (
        f"composite_score={score:.2f}",
        f"confidence={confidence:.2f}",
        f"thesis={item.thesis_signal}",
        f"risk={item.risk_level}",
    )
    return Decision(
        ticker=item.ticker.upper(),
        verdict=verdict_for(item, score),
        score=score,
        confidence=confidence,
        reasons=reasons,
        evidence=item.evidence,
    )
