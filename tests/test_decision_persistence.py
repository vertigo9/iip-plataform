from datetime import date

from iip.decision.models import Decision as EngineDecision
from iip.decision.models import EvidenceRef
from iip.decision.models import Verdict as EngineVerdict
from iip.decision.persistence import persist_decision_if_eligible
from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    PersistenceBatch,
    PersistenceCandidate,
    build_knowledge_evidence,
)
from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.models import Evidence
from iip.portfolio_decision.opportunity import build


def make_candidate(ticker: str, status: str = "IDENTITY_READY") -> PersistenceCandidate:
    observation = MetricObservationIdentity(
        canonical_ticker=ticker,
        original_ticker=ticker,
        metric_name="Distribuicao_Mensal",
        value="1.05",
        unit="BRL",
        scale="unit",
        period="2026-07",
        semantic_dimension=None,
        document_hash="abc123",
    )
    knowledge = build_knowledge_evidence(observation, title="t")
    return PersistenceCandidate(
        observation=observation,
        knowledge_evidence=knowledge,
        classification="",
        status=status,
        reason="promotion_gate_pass",
    )


def make_engine_decision(**overrides) -> EngineDecision:
    data = dict(
        ticker="PCIP11",
        verdict=EngineVerdict.COMPRAR,
        score=8.7,
        confidence=0.9,
        reasons=("composite_score=8.70",),
        evidence=(EvidenceRef("EV-PCIP11-001"),),
    )
    data.update(overrides)
    return EngineDecision(**data)


def make_bridge_with_evidence(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    bridge.persist_evidence(
        Evidence(
            evidence_id="EV-PCIP11-001",
            ticker="PCIP11",
            date=date(2026, 7, 31),
            source_type="atlas",
            source_url=None,
            relevant_facts=("x",),
        )
    )
    return bridge


def test_eligible_ticker_is_persisted_and_scoring_note_is_projected(tmp_path):
    bridge = make_bridge_with_evidence(tmp_path)
    batch = PersistenceBatch([make_candidate("PCIP11")])
    decision = make_engine_decision()

    outcome = persist_decision_if_eligible(
        decision,
        batch=batch,
        bridge=bridge,
        asset_class="FII",
        decision_id="DEC-PCIP11-20260731-001",
        date=date(2026, 7, 31),
        scoring_note="Opportunity Score: 7.88",
    )

    assert outcome.eligibility.eligible is True
    assert outcome.persisted is True
    assert outcome.decision_path.exists()
    assert outcome.scoring_note_path.exists()
    assert "01_Assets" in str(outcome.scoring_note_path)
    assert "Opportunity Score: 7.88" in outcome.scoring_note_path.read_text("utf-8")


def test_ineligible_ticker_persists_nothing(tmp_path):
    bridge = make_bridge_with_evidence(tmp_path)
    batch = PersistenceBatch([])  # no promoted observations for any ticker
    decision = make_engine_decision()

    outcome = persist_decision_if_eligible(
        decision,
        batch=batch,
        bridge=bridge,
        asset_class="FII",
        decision_id="DEC-PCIP11-20260731-002",
        date=date(2026, 7, 31),
        scoring_note="should never be written",
    )

    assert outcome.eligibility.eligible is False
    assert outcome.persisted is False
    assert outcome.knowledge_decision is None
    assert outcome.decision_path is None
    assert outcome.scoring_note_path is None
    assert list((tmp_path / "vault" / "03_Decisions").glob("*.md")) == []


def test_eligible_without_scoring_note_only_persists_decision(tmp_path):
    bridge = make_bridge_with_evidence(tmp_path)
    batch = PersistenceBatch([make_candidate("PCIP11")])
    decision = make_engine_decision()

    outcome = persist_decision_if_eligible(
        decision,
        batch=batch,
        bridge=bridge,
        asset_class="FII",
        decision_id="DEC-PCIP11-20260731-003",
        date=date(2026, 7, 31),
    )

    assert outcome.persisted is True
    assert outcome.decision_path.exists()
    assert outcome.scoring_note_path is None


def test_opportunity_is_formatted_automatically_into_scoring_note(tmp_path):
    bridge = make_bridge_with_evidence(tmp_path)
    batch = PersistenceBatch([make_candidate("PCIP11")])
    decision = make_engine_decision()
    opportunity = build("PCIP11", intrinsic_score=9.0, allocation_gap=0.5, income_need=0.5)

    outcome = persist_decision_if_eligible(
        decision,
        batch=batch,
        bridge=bridge,
        asset_class="FII",
        decision_id="DEC-PCIP11-20260731-004",
        date=date(2026, 7, 31),
        opportunity=opportunity,
    )

    assert outcome.scoring_note_path is not None
    content = outcome.scoring_note_path.read_text("utf-8")
    assert "7.88" in content


def test_explicit_scoring_note_takes_precedence_over_opportunity(tmp_path):
    bridge = make_bridge_with_evidence(tmp_path)
    batch = PersistenceBatch([make_candidate("PCIP11")])
    decision = make_engine_decision()
    opportunity = build("PCIP11", intrinsic_score=9.0, allocation_gap=0.5, income_need=0.5)

    outcome = persist_decision_if_eligible(
        decision,
        batch=batch,
        bridge=bridge,
        asset_class="FII",
        decision_id="DEC-PCIP11-20260731-005",
        date=date(2026, 7, 31),
        scoring_note="manual override",
        opportunity=opportunity,
    )

    content = outcome.scoring_note_path.read_text("utf-8")
    assert "manual override" in content
    assert "7.88" not in content
