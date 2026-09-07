"""Canonical document normalization before Atlas ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .provider_adapter import RawDocument


@dataclass(frozen=True)
class NormalizedDocument:
    document_id: str
    ticker: str
    title: str
    url: str
    category: str
    year: int | None
    provider: str
    content_hash: str | None


def normalize(document: RawDocument) -> NormalizedDocument:
    content_hash = (
        sha256(document.content).hexdigest() if document.content is not None else None
    )
    return NormalizedDocument(
        document_id=document.document_id,
        ticker=document.ticker.upper(),
        title=document.title.strip(),
        url=document.url.strip(),
        category=(document.category or "Outros").strip(),
        year=document.year,
        provider=document.provider or "unknown",
        content_hash=content_hash,
    )


def normalize_many(
    documents: tuple[RawDocument, ...],
) -> tuple[NormalizedDocument, ...]:
    return tuple(normalize(document) for document in documents)
