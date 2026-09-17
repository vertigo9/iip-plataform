"""Atlas -> Knowledge adapter for source documents."""

from __future__ import annotations

from datetime import date

from iip.knowledge.models import Evidence

from .models import AtlasDocument


class AtlasKnowledgeAdapter:
    def __init__(self, bridge) -> None:
        self.bridge = bridge

    @staticmethod
    def to_evidence(document: AtlasDocument) -> Evidence:
        evidence_date = (
            date(document.discovered_year, 12, 31)
            if document.discovered_year is not None
            else document.ingested_at.date()
        )
        return Evidence(
            evidence_id=document.document_id,
            ticker=document.ticker,
            date=evidence_date,
            source_type="atlas",
            source_url=document.final_url or document.url,
            title=document.title,
            document_hash=document.content_hash,
            relevant_facts=(
                f"provider={document.provider}",
                f"role={document.role}",
                f"content_type={document.content_type}",
                f"status_code={document.status_code}",
                f"document_id={document.document_id}",
            ),
        )

    def persist(self, document: AtlasDocument):
        evidence = self.to_evidence(document)
        try:
            persisted = self.bridge.persist_evidence(evidence)
        except FileExistsError:
            # The evidence store is append-only. A repeated identical source
            # should still reach the idempotent projection stage.
            persisted = None

        sync = getattr(self.bridge, "sync_evidence_projection", None)
        if sync is not None:
            return sync(evidence)
        return evidence if persisted is None else persisted

    def persist_many(self, documents: tuple[AtlasDocument, ...]):
        return tuple(self.persist(document) for document in documents)
