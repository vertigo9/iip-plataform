"""Evidence lineage from source document to intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceLink:
    evidence_id: str
    document_id: str
    provider: str
    source_url: str
    claim_type: str


@dataclass(frozen=True)
class EvidenceChain:
    links: tuple[EvidenceLink, ...] = ()

    def add(self, link: EvidenceLink) -> EvidenceChain:
        if link.evidence_id in {item.evidence_id for item in self.links}:
            return self
        return EvidenceChain(self.links + (link,))
