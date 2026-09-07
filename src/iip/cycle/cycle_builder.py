"""Build a closed portfolio decision cycle from explicit inputs."""

from __future__ import annotations

from .decision_adapter import normalize_decision
from .evidence_bridge import evidence_ready
from .income_bridge import normalize_income
from .models import (
    CycleObservation,
    CycleStatus,
    PortfolioAssetInput,
    PortfolioCycle,
)


def build_cycle(
    cycle_id: str,
    as_of: str,
    assets: tuple[PortfolioAssetInput, ...],
) -> PortfolioCycle:
    observations = []
    degraded = False

    for asset in assets:
        ticker, score, confidence, action = normalize_decision(
            asset.ticker,
            score=asset.score,
            confidence=asset.confidence,
            action=asset.action,
        )
        evidence_ok = evidence_ready(asset.evidence_ids)
        if action in {"APORTAR", "COMPRAR"} and not evidence_ok:
            degraded = True

        observations.append(
            CycleObservation(
                ticker=ticker,
                score=score,
                confidence=confidence,
                action=action,
                weight=round(asset.weight, 12),
                annual_income=normalize_income(asset.annual_income),
                evidence_count=len(tuple(dict.fromkeys(asset.evidence_ids))),
            )
        )

    status = CycleStatus.DEGRADED if degraded else CycleStatus.READY
    return PortfolioCycle(cycle_id, as_of, tuple(observations), status)
