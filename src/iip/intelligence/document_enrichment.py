"""Deterministic enrichment metadata for normalized documents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnrichedDocument:
    document_id: str
    category: str
    period: str | None = None
    tags: tuple[str, ...] = ()


def enrich(
    document_id: str,
    category: str,
    *,
    period: str | None = None,
    tags: tuple[str, ...] = (),
) -> EnrichedDocument:
    clean_tags = tuple(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
    return EnrichedDocument(
        document_id=document_id,
        category=category.strip() or "Outros",
        period=period,
        tags=clean_tags,
    )
