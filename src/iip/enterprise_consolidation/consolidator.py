"""Cross-portfolio consolidation engine."""

from __future__ import annotations

from .models import ConsolidationInput, ConsolidationResult


def consolidate(data: ConsolidationInput) -> ConsolidationResult:
    identifiers = {(item.portfolio_id, item.version) for item in data.portfolios}
    unique_ids = {item.portfolio_id for item in data.portfolios}
    consistent = (
        len(unique_ids) == len(data.portfolios)
        and data.provider_count >= 0
        and data.evidence_count >= 0
        and data.decision_count >= 0
        and bool(data.portfolios) == bool(unique_ids)
    )
    return ConsolidationResult(
        portfolio_count=len(data.portfolios),
        unique_portfolios=len(unique_ids),
        provider_count=data.provider_count,
        evidence_count=data.evidence_count,
        decision_count=data.decision_count,
        consistent=consistent and len(identifiers) == len(data.portfolios),
    )
