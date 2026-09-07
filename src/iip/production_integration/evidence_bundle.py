"""Portable evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceBundle:
    decision_id: str
    source_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return (
            bool(self.decision_id)
            and bool(self.source_ids)
            and bool(self.observation_ids)
        )


def normalize(bundle: EvidenceBundle) -> EvidenceBundle:
    return EvidenceBundle(
        bundle.decision_id.strip(),
        tuple(dict.fromkeys(bundle.source_ids)),
        tuple(dict.fromkeys(bundle.document_ids)),
        tuple(dict.fromkeys(bundle.observation_ids)),
    )
