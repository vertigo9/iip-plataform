from iip.intelligence.decision_eligibility import check_ticker_eligibility
from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    PersistenceBatch,
    PersistenceCandidate,
    build_knowledge_evidence,
)


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


def test_ticker_with_ready_observation_is_eligible():
    batch = PersistenceBatch([make_candidate("PCIP11")])

    result = check_ticker_eligibility(batch, "pcip11")

    assert result.eligible is True
    assert result.ticker == "PCIP11"
    assert result.reason == "has_promoted_observation"


def test_ticker_without_any_observation_is_not_eligible():
    batch = PersistenceBatch([make_candidate("PCIP11")])

    result = check_ticker_eligibility(batch, "XPML11")

    assert result.eligible is False
    assert result.reason == "no_promoted_observation_for_ticker"


def test_ticker_with_only_blocked_observation_is_not_eligible():
    batch = PersistenceBatch([make_candidate("PCIP11", status="BLOCKED")])

    result = check_ticker_eligibility(batch, "PCIP11")

    assert result.eligible is False
    assert result.reason == "no_promoted_observation_for_ticker"


def test_ticker_with_dimension_ready_status_is_eligible():
    batch = PersistenceBatch(
        [make_candidate("PCIP11", status="IDENTITY_READY_WITH_DIMENSION")]
    )

    result = check_ticker_eligibility(batch, "PCIP11")

    assert result.eligible is True


def test_empty_ticker_is_rejected():
    batch = PersistenceBatch([make_candidate("PCIP11")])

    result = check_ticker_eligibility(batch, "   ")

    assert result.eligible is False
    assert result.reason == "empty_ticker"
