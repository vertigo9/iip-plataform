"""Consolidated cycle report."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PortfolioCycle


@dataclass(frozen=True)
class CycleReport:
    cycle_id: str
    as_of: str
    status: str
    total_assets: int
    evidence_ready_assets: int
    buy_candidates: int
    annual_income: float


def render(cycle: PortfolioCycle, buy_candidates: int) -> CycleReport:
    return CycleReport(
        cycle_id=cycle.cycle_id,
        as_of=cycle.as_of,
        status=cycle.status.value,
        total_assets=len(cycle.observations),
        evidence_ready_assets=sum(o.evidence_count > 0 for o in cycle.observations),
        buy_candidates=buy_candidates,
        annual_income=round(sum(o.annual_income for o in cycle.observations), 12),
    )
