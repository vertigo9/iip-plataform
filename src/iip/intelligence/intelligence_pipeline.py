"""End-to-end intelligence staging over normalized Atlas evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .document_classification import ClassifiedDocument, classify_title
from .document_enrichment import EnrichedDocument, enrich
from .evidence_chain import EvidenceChain, EvidenceLink


@dataclass(frozen=True)
class IntelligenceDocument:
    classified: ClassifiedDocument
    enriched: EnrichedDocument
    evidence: EvidenceChain


def stage_document(
    document_id: str,
    ticker: str,
    title: str,
    provider: str,
    source_url: str,
    category: str,
    *,
    period: str | None = None,
    tags: tuple[str, ...] = (),
) -> IntelligenceDocument:
    classified = classify_title(document_id, ticker, title, provider)
    enriched = enrich(document_id, category, period=period, tags=tags)
    evidence = EvidenceChain().add(
        EvidenceLink(
            evidence_id=f"{provider}:{document_id}",
            document_id=document_id,
            provider=provider,
            source_url=source_url,
            claim_type=classified.document_type.value,
        )
    )
    return IntelligenceDocument(classified, enriched, evidence)
