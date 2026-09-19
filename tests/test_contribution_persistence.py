from datetime import date

from iip.decision.contribution_persistence import persist_contributions_if_eligible
from iip.integration.contribution import ContributionCandidate
from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    PersistenceBatch,
    PersistenceCandidate,
    build_knowledge_evidence,
)
from iip.knowledge.bridge import KnowledgeBridge


def make_metric_candidate(
    ticker: str, status: str = "IDENTITY_READY"
) -> PersistenceCandidate:
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


def test_eligible_candidates_are_persisted_with_correct_asset_class(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    batch = PersistenceBatch(
        [make_metric_candidate("PCIP11"), make_metric_candidate("XPML11")]
    )
    candidates = (
        ContributionCandidate(ticker="PCIP11", score=8.5, monthly_budget_share=0.6),
        ContributionCandidate(ticker="XPML11", score=6.0, monthly_budget_share=0.4),
    )

    outcomes = persist_contributions_if_eligible(
        candidates,
        batch=batch,
        bridge=bridge,
        asset_classes={"PCIP11": "FII", "XPML11": "FII"},
        date=date(2026, 7, 31),
    )

    assert len(outcomes) == 2
    assert all(o.persisted for o in outcomes)
    assert all(o.note_path.exists() for o in outcomes)
    pcip11_content = next(
        o for o in outcomes if o.ticker == "PCIP11"
    ).note_path.read_text("utf-8")
    assert "60.00%" in pcip11_content


def test_ineligible_ticker_is_skipped_not_raised(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    batch = PersistenceBatch([make_metric_candidate("PCIP11")])
    candidates = (
        ContributionCandidate(ticker="PCIP11", score=8.5, monthly_budget_share=1.0),
        ContributionCandidate(ticker="XPML11", score=6.0, monthly_budget_share=0.0),
    )

    outcomes = persist_contributions_if_eligible(
        candidates,
        batch=batch,
        bridge=bridge,
        asset_classes={"PCIP11": "FII", "XPML11": "FII"},
        date=date(2026, 7, 31),
    )

    pcip11 = next(o for o in outcomes if o.ticker == "PCIP11")
    xpml11 = next(o for o in outcomes if o.ticker == "XPML11")
    assert pcip11.persisted is True
    assert xpml11.persisted is False
    assert xpml11.eligibility.reason == "no_promoted_observation_for_ticker"
    assert xpml11.note_path is None


def test_missing_asset_class_is_skipped_not_raised(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    batch = PersistenceBatch([make_metric_candidate("PCIP11")])
    candidates = (
        ContributionCandidate(ticker="PCIP11", score=8.5, monthly_budget_share=1.0),
    )

    outcomes = persist_contributions_if_eligible(
        candidates,
        batch=batch,
        bridge=bridge,
        asset_classes={},  # no mapping supplied
        date=date(2026, 7, 31),
    )

    assert outcomes[0].persisted is False
    assert outcomes[0].eligibility.reason == "missing_asset_class"


def test_empty_candidates_returns_empty_outcomes(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    batch = PersistenceBatch([])

    outcomes = persist_contributions_if_eligible(
        (), batch=batch, bridge=bridge, asset_classes={}, date=date(2026, 7, 31)
    )

    assert outcomes == ()
