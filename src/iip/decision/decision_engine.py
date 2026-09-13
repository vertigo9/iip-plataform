"""Decision engine: evidence -> score -> verdict."""

from __future__ import annotations

from .models import Decision, IntelligenceInput, Verdict
from .scoring import composite_score, confidence_score
from .thesis_exit_gate import ThesisExitState


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

    verdict = verdict_for(item, score)

    thesis_exit = getattr(item, "thesis_exit", None)
    thesis_exit_reason = None

    if thesis_exit is not None:
        thesis_exit_reason = (
            f"thesis_exit={thesis_exit.state.value}",
            f"thesis_exit_failed={','.join(thesis_exit.failed_gates) or 'none'}",
            f"thesis_exit_attention={','.join(thesis_exit.attention_gates) or 'none'}",
        )

        if thesis_exit.state is ThesisExitState.BREAK:
            verdict = Verdict.VENDER

    reasons = (
        f"composite_score={score:.2f}",
        f"confidence={confidence:.2f}",
        f"thesis={item.thesis_signal}",
        f"risk={item.risk_level}",
    )

    if thesis_exit_reason is not None:
        reasons = reasons + thesis_exit_reason

    return Decision(
        ticker=item.ticker.upper(),
        verdict=verdict,
        score=score,
        confidence=confidence,
        reasons=reasons,
        evidence=item.evidence,
        thesis_exit=thesis_exit,
    )
