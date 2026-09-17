"""Capital allocation ranking from normalized decision signals."""

from __future__ import annotations

from .models import AssetSignal, PortfolioConstraint, PortfolioDecision


def allocation_score(signal: AssetSignal) -> float:
    risk_adjustment = max(0.0, min(2.0, signal.confidence))
    return round(signal.decision_score * risk_adjustment, 2)


def rank(
    signals: tuple[AssetSignal, ...],
) -> tuple[PortfolioDecision, ...]:
    decisions = tuple(
        PortfolioDecision(
            ticker=s.ticker,
            action=s.action,
            allocation_score=allocation_score(s),
            rationale=f"score={s.decision_score:.2f};confidence={s.confidence:.2f}",
            thesis_exit_state=s.thesis_exit_state,
            thesis_exit_failed_gates=s.thesis_exit_failed_gates,
            thesis_exit_attention_gates=s.thesis_exit_attention_gates,
            thesis_exit_unknown_gates=s.thesis_exit_unknown_gates,
            thesis_exit_critical_failure=s.thesis_exit_critical_failure,
        )
        for s in signals
    )
    return tuple(
        sorted(
            decisions,
            key=lambda item: (-item.allocation_score, item.ticker),
        )
    )


def apply_constraints(
    decisions: tuple[PortfolioDecision, ...],
    constraints: tuple[PortfolioConstraint, ...],
) -> tuple[PortfolioDecision, ...]:
    # Constraints are represented but do not invent allocation weights.
    # Actual portfolio weights are supplied by the caller in a later stage.
    return decisions
