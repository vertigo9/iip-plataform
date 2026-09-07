from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from .metric_identity import MetricObservationIdentity


@dataclass(frozen=True)
class KnowledgeMetricEvidence:
    evidence_id: str
    ticker: str
    date: date
    source_type: str
    source_url: str | None
    title: str
    document_hash: str
    relevant_facts: dict[str, str]


@dataclass(frozen=True)
class PersistenceCandidate:
    observation: MetricObservationIdentity
    knowledge_evidence: KnowledgeMetricEvidence
    classification: str
    status: str
    reason: str


@dataclass
class PersistenceBatch:
    candidates: list[PersistenceCandidate] = field(default_factory=list)

    @property
    def ready(self) -> list[PersistenceCandidate]:
        return [
            candidate
            for candidate in self.candidates
            if candidate.status
            in {
                "IDENTITY_READY",
                "IDENTITY_READY_WITH_DIMENSION",
                "DEDUPLICABLE",
            }
        ]

    @property
    def blocked(self) -> list[PersistenceCandidate]:
        return [
            candidate
            for candidate in self.candidates
            if candidate.status
            not in {
                "IDENTITY_READY",
                "IDENTITY_READY_WITH_DIMENSION",
                "DEDUPLICABLE",
            }
        ]


class DuplicatePolicy:
    """Pure identity/idempotency decisions. Does not perform persistence."""

    @staticmethod
    def canonical_groups(
        candidates: Iterable[PersistenceCandidate],
    ) -> dict[str, list[PersistenceCandidate]]:
        groups: dict[str, list[PersistenceCandidate]] = {}
        for candidate in candidates:
            key = candidate.observation.observation_key
            groups.setdefault(key, []).append(candidate)
        return groups

    @staticmethod
    def distinct_value_collisions(
        candidates: Iterable[PersistenceCandidate],
    ) -> dict[str, list[PersistenceCandidate]]:
        result: dict[str, list[PersistenceCandidate]] = {}
        for key, group in DuplicatePolicy.canonical_groups(candidates).items():
            values = {item.observation.value for item in group}
            if len(values) > 1:
                result[key] = group
        return result


def metric_evidence_id(observation: MetricObservationIdentity) -> str:
    """Stable ID incorporating semantic identity, not row number."""
    payload = observation.canonical_payload()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"metric:{observation.canonical_ticker}:{observation.period}:{observation.metric_name}:{digest}"


def knowledge_evidence_id(metric_id: str) -> str:
    digest = hashlib.sha256(metric_id.encode("utf-8")).hexdigest()[:24]
    return f"evidence:metric:{digest}"


def month_date(period: str) -> date:
    year, month = period.split("-", 1)
    return date(int(year), int(month), 1)


def build_knowledge_evidence(
    observation: MetricObservationIdentity,
    *,
    title: str,
    source_type: str = "historical_metric",
    source_url: str | None = None,
    relevant_facts: dict[str, str] | None = None,
) -> KnowledgeMetricEvidence:
    metric_id = metric_evidence_id(observation)
    facts = {
        "metric": observation.metric_name,
        "value": observation.value,
        "unit": observation.unit or "",
        "scale": observation.scale or "",
        "period": observation.period,
        "semantic_dimension": observation.semantic_dimension or "",
        "canonical_ticker": observation.canonical_ticker,
        "original_ticker": observation.original_ticker or "",
        "document_hash": observation.document_hash,
        "document_id": observation.document_id or "",
        "source_locator": observation.source_locator or "",
        "lineage": observation.lineage or "",
    }
    if relevant_facts:
        facts.update(relevant_facts)

    return KnowledgeMetricEvidence(
        evidence_id=knowledge_evidence_id(metric_id),
        ticker=observation.canonical_ticker,
        date=month_date(observation.period),
        source_type=source_type,
        source_url=source_url,
        title=title,
        document_hash=observation.document_hash,
        relevant_facts=facts,
    )
