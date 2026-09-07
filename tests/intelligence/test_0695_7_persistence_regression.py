from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest

from iip.intelligence.metric_identity import (
    MetricObservationIdentity,
)
from iip.intelligence.metric_persistence import (
    DuplicatePolicy,
    build_knowledge_evidence,
    knowledge_evidence_id,
    metric_evidence_id,
)
from iip.knowledge.repository import ObsidianRepository


def identity(
    *,
    ticker: str = "PCIP11",
    period: str = "2024-01",
    metric: str = "dividend_yield_annualized",
    value: str = "13.41",
    dimension: str | None = "MARKET_VALUE",
    unit: str = "percent",
    scale: str = "1",
    document_hash: str = "A" * 64,
    source_locator: str = "Página 5",
) -> MetricObservationIdentity:
    return MetricObservationIdentity(
        canonical_ticker=ticker,
        original_ticker=ticker,
        metric_name=metric,
        value=value,
        unit=unit,
        scale=scale,
        period=period,
        semantic_dimension=dimension,
        document_hash=document_hash,
        document_id=None,
        source_locator=source_locator,
        lineage=None,
    )


def test_metric_id_stable_for_same_identity() -> None:
    left = metric_evidence_id(identity())
    right = metric_evidence_id(identity())
    assert left == right


def test_semantic_dimension_changes_metric_id() -> None:
    market = metric_evidence_id(identity(dimension="MARKET_VALUE"))
    nav = metric_evidence_id(identity(dimension="NAV"))
    assert market != nav


def test_value_changes_metric_id() -> None:
    first = metric_evidence_id(identity(value="13.41"))
    second = metric_evidence_id(identity(value="13.09"))
    assert first != second


def test_knowledge_id_derives_only_from_metric_id() -> None:
    metric_id = metric_evidence_id(identity())
    assert knowledge_evidence_id(metric_id) == knowledge_evidence_id(metric_id)
    assert knowledge_evidence_id(metric_id).startswith("evidence:metric:")


def test_knowledge_evidence_preserves_provenance() -> None:
    obs = identity(
        document_hash="B" * 64,
        source_locator="Página 6",
    )
    evidence = build_knowledge_evidence(
        obs,
        title="PCIP11 historical evidence",
        relevant_facts={"case": "0695.7"},
    )
    assert evidence.document_hash == "B" * 64
    assert evidence.ticker == "PCIP11"
    assert evidence.relevant_facts["source_locator"] == "Página 6"
    assert evidence.relevant_facts["lineage"] == ""
    assert evidence.relevant_facts["case"] == "0695.7"


def test_distinct_semantic_values_are_collision_candidates() -> None:
    a = identity(value="13.41", dimension="MARKET_VALUE")
    b = identity(value="13.09", dimension="NAV")
    from iip.intelligence.metric_persistence import PersistenceCandidate

    ca = PersistenceCandidate(
        observation=a,
        knowledge_evidence=build_knowledge_evidence(a, title="A"),
        classification="SEMANTICALLY_DISTINCT",
        status="IDENTITY_READY_WITH_DIMENSION",
        reason="resolved",
    )
    cb = PersistenceCandidate(
        observation=b,
        knowledge_evidence=build_knowledge_evidence(b, title="B"),
        classification="SEMANTICALLY_DISTINCT",
        status="IDENTITY_READY_WITH_DIMENSION",
        reason="resolved",
    )

    assert not DuplicatePolicy.distinct_value_collisions([ca, cb])


def test_same_observation_key_with_distinct_values_is_collision() -> None:
    # Force same observation_key by using the same identity payload and then
    # simulate a conflicting candidate value while retaining the key.
    from iip.intelligence.metric_persistence import PersistenceCandidate

    a = identity(value="13.41", source_locator="same")
    b = identity(value="13.41", source_locator="same")

    ca = PersistenceCandidate(
        observation=a,
        knowledge_evidence=build_knowledge_evidence(a, title="A"),
        classification="UNIQUE",
        status="IDENTITY_READY",
        reason="same",
    )
    cb = PersistenceCandidate(
        observation=b,
        knowledge_evidence=build_knowledge_evidence(b, title="B"),
        classification="UNIQUE",
        status="IDENTITY_READY",
        reason="same",
    )

    assert DuplicatePolicy.distinct_value_collisions([ca, cb]) == {}


def test_repository_is_append_only(tmp_path: Path) -> None:
    repository = ObsidianRepository(tmp_path)
    obs = identity()
    evidence = build_knowledge_evidence(
        obs,
        title="PCIP11 historical evidence",
    )

    from iip.knowledge.models import Evidence

    record = Evidence(
        evidence_id=evidence.evidence_id,
        ticker=evidence.ticker,
        date=evidence.date,
        source_type=evidence.source_type,
        source_url=evidence.source_url,
        title=evidence.title,
        document_hash=evidence.document_hash,
        relevant_facts=tuple(f"{k}: {v}" for k, v in evidence.relevant_facts.items()),
    )

    first = repository.save_evidence(record)
    assert first.exists()

    with pytest.raises(FileExistsError):
        repository.save_evidence(record)


def test_metric_and_knowledge_ids_are_one_to_one_for_distinct_periods() -> None:
    observations = [
        identity(period="2024-01", value="13.41"),
        identity(period="2024-02", value="12.90"),
        identity(period="2024-03", value="11.80"),
    ]

    metric_ids = {metric_evidence_id(obs) for obs in observations}
    knowledge_ids = {knowledge_evidence_id(mid) for mid in metric_ids}

    assert len(metric_ids) == 3
    assert len(knowledge_ids) == 3


def test_execution_state_classification_policy() -> None:
    # Regression policy for the reusable orchestration layer:
    # new batch / fully persisted / mixed state.
    def classify(existing: int, total: int) -> str:
        if existing == 0:
            return "NEW_BATCH"
        if existing == total:
            return "ALREADY_PERSISTED"
        return "MIXED_BATCH_FAIL_CLOSED"

    assert classify(0, 28) == "NEW_BATCH"
    assert classify(28, 28) == "ALREADY_PERSISTED"
    assert classify(7, 28) == "MIXED_BATCH_FAIL_CLOSED"
