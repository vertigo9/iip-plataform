"""Persist normalized operational documents as Knowledge evidence."""

from __future__ import annotations

from datetime import date

from iip.knowledge.models import Evidence

from .normalization import NormalizedDocument


class OperationalEvidenceSink:
    """Translate discovery output into the existing Knowledge persistence path."""

    def __init__(self, bridge) -> None:
        self.bridge = bridge

    @staticmethod
    def to_evidence(document: NormalizedDocument) -> Evidence:
        evidence_date = (
            date(document.year, 12, 31)
            if document.year is not None
            else date.today()
        )
        return Evidence(
            evidence_id=document.document_id,
            ticker=document.ticker,
            date=evidence_date,
            source_type=document.provider or "operational",
            source_url=document.url,
            title=document.title,
            document_hash=document.content_hash,
            relevant_facts=(
                f"provider={document.provider or 'unknown'}",
                f"category={document.category}",
                f"document_id={document.document_id}",
            ),
        )

    def persist(self, document: NormalizedDocument):
        evidence = self.to_evidence(document)
        try:
            persisted = self.bridge.persist_evidence(evidence)
        except FileExistsError:
            persisted = None

        sync = getattr(self.bridge, "sync_evidence_projection", None)
        if sync is not None:
            return sync(evidence)
        return evidence if persisted is None else persisted
