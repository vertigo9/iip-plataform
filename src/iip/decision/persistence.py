"""Persist a decision-engine Decision only when its ticker has promoted
(Promotion-Gate-eligible) evidence behind it.

Composition, not new logic: reuses
``intelligence.decision_eligibility.check_ticker_eligibility`` for the
gate check, ``decision.knowledge_bridge.to_knowledge_decision`` for the
model conversion, and ``KnowledgeBridge`` (already wired to
``AssetVaultLocator`` via its projector) for the actual writes. Nothing
here talks to ``ObsidianRepository.asset_location`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

from iip.intelligence.decision_eligibility import (
    EligibilityResult,
    check_ticker_eligibility,
)
from iip.intelligence.metric_persistence import PersistenceBatch
from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.models import Decision as KnowledgeDecision
from iip.knowledge.models import Verdict as KnowledgeVerdict
from iip.portfolio_decision.opportunity import Opportunity

from .knowledge_bridge import to_knowledge_decision
from .models import Decision as EngineDecision
from .scoring_note import format_opportunity_note


@dataclass(frozen=True)
class DecisionPersistenceOutcome:
    eligibility: EligibilityResult
    persisted: bool
    knowledge_decision: KnowledgeDecision | None
    decision_path: Path | None
    scoring_note_path: Path | None


def persist_decision_if_eligible(
    decision: EngineDecision,
    *,
    batch: PersistenceBatch,
    bridge: KnowledgeBridge,
    asset_class: str,
    decision_id: str,
    date: _date,
    previous_verdict: KnowledgeVerdict | None = None,
    scoring_note: str | None = None,
    opportunity: Opportunity | None = None,
) -> DecisionPersistenceOutcome:
    """Persist ``decision`` and project a scoring note, but only if the
    ticker has at least one Promotion-Gate-eligible observation in
    ``batch``.

    When not eligible, nothing is written — the decision is computed in
    memory only (same posture as ``DryRunPersistenceAdapter`` for metrics).
    The scoring note comes from one of two sources: pass ``scoring_note``
    directly for custom text, or pass ``opportunity`` (the canonical
    ``portfolio_decision.opportunity.Opportunity``) to have it formatted
    automatically via ``format_opportunity_note``. An explicit
    ``scoring_note`` takes precedence if both are given. Neither given
    means no scoring note is projected.
    """

    eligibility = check_ticker_eligibility(batch, decision.ticker)

    if not eligibility.eligible:
        return DecisionPersistenceOutcome(
            eligibility=eligibility,
            persisted=False,
            knowledge_decision=None,
            decision_path=None,
            scoring_note_path=None,
        )

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id=decision_id,
        date=date,
        previous_verdict=previous_verdict,
    )

    decision_path = bridge.persist_decision(knowledge_decision)

    note = scoring_note
    if note is None and opportunity is not None:
        note = format_opportunity_note(opportunity, as_of=date)

    scoring_note_path = None
    if note is not None:
        scoring_note_path = bridge.sync_asset_section(
            eligibility.ticker,
            asset_class,
            "scoring",
            "opportunity_score",
            note,
        ).path

    return DecisionPersistenceOutcome(
        eligibility=eligibility,
        persisted=True,
        knowledge_decision=knowledge_decision,
        decision_path=decision_path,
        scoring_note_path=scoring_note_path,
    )
