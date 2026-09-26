"""Bridge between the decision engine's Decision and the persisted
(knowledge) Decision.

Two distinct ``Decision`` dataclasses exist in this codebase:

- ``iip.decision.models.Decision`` — the decision engine's output
  (ticker, verdict, score, confidence, reasons, evidence).
- ``iip.knowledge.models.Decision`` — what ``KnowledgeBridge.persist_decision``
  writes to the vault (decision_id, date, new_verdict, change_type,
  evidence_ids, ...).

Nothing in the codebase converted between the two before this module.
"""

from __future__ import annotations

from datetime import date as _date

from iip.knowledge.models import Decision as KnowledgeDecision
from iip.knowledge.models import DecisionChange
from iip.knowledge.models import Verdict as KnowledgeVerdict

from .models import Decision as EngineDecision
from .models import Verdict as EngineVerdict

# The two Verdict enums are not the same shape:
#   - EngineVerdict has VENDER, which KnowledgeVerdict does not.
#   - KnowledgeVerdict has AUMENTAR and ENCERRAR, which EngineVerdict does
#     not produce.
# VENDER ("sell") maps to ENCERRAR ("close position") as the closest
# semantic match. AUMENTAR has no producer on the engine side today — it
# remains a valid value for other (e.g. manual) writers of Decision, just
# unreachable through this bridge.
_VERDICT_MAP: dict[EngineVerdict, KnowledgeVerdict] = {
    EngineVerdict.COMPRAR: KnowledgeVerdict.COMPRAR,
    EngineVerdict.MANTER: KnowledgeVerdict.MANTER,
    EngineVerdict.AGUARDAR: KnowledgeVerdict.AGUARDAR,
    EngineVerdict.REDUZIR: KnowledgeVerdict.REDUZIR,
    EngineVerdict.VENDER: KnowledgeVerdict.ENCERRAR,
}


def to_knowledge_verdict(verdict: EngineVerdict) -> KnowledgeVerdict:
    return _VERDICT_MAP[verdict]


def _infer_change_type(
    new_verdict: KnowledgeVerdict,
    previous_verdict: KnowledgeVerdict | None,
) -> DecisionChange:
    if previous_verdict is None or previous_verdict == new_verdict:
        return DecisionChange.NO_CHANGE

    order = (
        KnowledgeVerdict.ENCERRAR,
        KnowledgeVerdict.REDUZIR,
        KnowledgeVerdict.AGUARDAR,
        KnowledgeVerdict.MANTER,
        KnowledgeVerdict.COMPRAR,
        KnowledgeVerdict.AUMENTAR,
    )
    return (
        DecisionChange.UPGRADE
        if order.index(new_verdict) > order.index(previous_verdict)
        else DecisionChange.DOWNGRADE
    )


def to_knowledge_decision(
    decision: EngineDecision,
    *,
    decision_id: str,
    date: _date,
    previous_verdict: KnowledgeVerdict | None = None,
    change_type: DecisionChange | None = None,
) -> KnowledgeDecision:
    """Convert an engine Decision into the persistable knowledge Decision.

    ``change_type`` is inferred from ``previous_verdict`` when not given
    explicitly. Pass ``change_type`` directly when the thesis itself
    changed (THESIS_CHANGE), since that cannot be inferred from the
    verdict ordering alone.
    """

    new_verdict = to_knowledge_verdict(decision.verdict)

    return KnowledgeDecision(
        decision_id=decision_id,
        ticker=decision.ticker.upper(),
        date=date,
        new_verdict=new_verdict,
        previous_verdict=previous_verdict,
        change_type=(
            change_type
            if change_type is not None
            else _infer_change_type(new_verdict, previous_verdict)
        ),
        confidence=decision.confidence,
        reasons=decision.reasons,
        evidence_ids=tuple(ref.evidence_id for ref in decision.evidence),
        thesis_exit_state=(
            decision.thesis_exit.state.value
            if decision.thesis_exit is not None
            else None
        ),
        thesis_exit_failed_gates=(
            tuple(decision.thesis_exit.failed_gates)
            if decision.thesis_exit is not None
            else ()
        ),
        thesis_exit_attention_gates=(
            tuple(decision.thesis_exit.attention_gates)
            if decision.thesis_exit is not None
            else ()
        ),
        thesis_exit_unknown_gates=(
            tuple(decision.thesis_exit.unknown_gates)
            if decision.thesis_exit is not None
            else ()
        ),
        decision_score=decision.score,
        thesis_exit_critical_failure=(
            decision.thesis_exit.critical_failure
            if decision.thesis_exit is not None
            else None
        ),
    )
