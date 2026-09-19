"""Projection from an economic Decision into the portfolio AssetSignal contract."""

from __future__ import annotations

from iip.decision.models import Decision, Verdict
from iip.portfolio.registry import PortfolioAsset

from .models import Action, AssetSignal

_VERDICT_TO_ACTION: dict[Verdict, Action] = {
    Verdict.COMPRAR: Action.APORTAR,
    Verdict.MANTER: Action.MANTER,
    Verdict.AGUARDAR: Action.AGUARDAR,
    Verdict.REDUZIR: Action.REDUZIR,
    Verdict.VENDER: Action.VENDER,
}


def _unique_evidence_ids(decision: Decision) -> tuple[str, ...]:
    """Return evidence IDs in source order, removing duplicates."""
    seen: set[str] = set()
    result: list[str] = []

    for reference in decision.evidence:
        evidence_id = reference.evidence_id
        if evidence_id not in seen:
            seen.add(evidence_id)
            result.append(evidence_id)

    return tuple(result)


def decision_to_asset_signal(
    decision: Decision,
    asset: PortfolioAsset,
) -> AssetSignal:
    """Project an economic Decision into the existing AssetSignal contract.

    This function transports existing decision information only. It does not
    recalculate scores, confidence, Thesis Exit, or portfolio actions.
    """
    evidence_ids = _unique_evidence_ids(decision)
    thesis_exit = decision.thesis_exit

    return AssetSignal(
        ticker=decision.ticker,
        asset_class=asset.asset_class,
        decision_score=decision.score,
        confidence=decision.confidence,
        action=_VERDICT_TO_ACTION[decision.verdict],
        evidence_count=len(evidence_ids),
        evidence_ids=evidence_ids,
        thesis_exit_state=(
            thesis_exit.state.value
            if thesis_exit is not None
            else None
        ),
        thesis_exit_failed_gates=(
            tuple(thesis_exit.failed_gates)
            if thesis_exit is not None
            else ()
        ),
        thesis_exit_attention_gates=(
            tuple(thesis_exit.attention_gates)
            if thesis_exit is not None
            else ()
        ),
        thesis_exit_unknown_gates=(
            tuple(thesis_exit.unknown_gates)
            if thesis_exit is not None
            else ()
        ),
        thesis_exit_critical_failure=(
            thesis_exit.critical_failure
            if thesis_exit is not None
            else None
        ),
    )
