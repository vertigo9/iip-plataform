"""Data-quality gates for operational ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from .normalization import NormalizedDocument


@dataclass(frozen=True)
class QualityResult:
    valid: bool
    errors: tuple[str, ...] = ()


def validate_document(document: NormalizedDocument) -> QualityResult:
    errors: list[str] = []
    if not document.document_id:
        errors.append("missing_document_id")
    if not document.ticker:
        errors.append("missing_ticker")
    if not document.title:
        errors.append("missing_title")
    if not document.url:
        errors.append("missing_url")
    if not document.provider or document.provider == "unknown":
        errors.append("missing_provider")
    return QualityResult(not errors, tuple(errors))
