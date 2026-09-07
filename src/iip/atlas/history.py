"""Multi-document historical normalization for Atlas."""

from __future__ import annotations

from dataclasses import dataclass

from .models import AtlasDocument


@dataclass(frozen=True)
class HistoryBatch:
    """Deterministic result of a multi-year/multi-document normalization."""

    documents: tuple[AtlasDocument, ...]
    duplicates: tuple[AtlasDocument, ...]
    years: tuple[int, ...]


class AtlasHistoryProcessor:
    """Deduplicate Atlas documents while preserving first-seen order.

    Two documents are considered duplicates only when their canonical
    ``document_id`` is identical. This intentionally keeps different years
    and different content as separate historical records.
    """

    @staticmethod
    def process(documents: tuple[AtlasDocument, ...]) -> HistoryBatch:
        seen: set[str] = set()
        unique: list[AtlasDocument] = []
        duplicates: list[AtlasDocument] = []

        for document in documents:
            if document.document_id in seen:
                duplicates.append(document)
            else:
                seen.add(document.document_id)
                unique.append(document)

        years = tuple(
            sorted(
                {
                    document.discovered_year
                    for document in unique
                    if document.discovered_year is not None
                }
            )
        )

        return HistoryBatch(
            documents=tuple(unique),
            duplicates=tuple(duplicates),
            years=years,
        )
