"""Closed-loop portfolio pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .allocation_bridge import eligible_candidates
from .cycle_builder import build_cycle
from .models import PortfolioAssetInput, PortfolioCycle
from .report import CycleReport, render


@dataclass(frozen=True)
class CycleResult:
    cycle: PortfolioCycle
    report: CycleReport


def run(
    cycle_id: str,
    as_of: str,
    assets: tuple[PortfolioAssetInput, ...],
) -> CycleResult:
    cycle = build_cycle(cycle_id, as_of, assets)
    candidates = eligible_candidates(cycle.observations)
    return CycleResult(
        cycle=cycle,
        report=render(cycle, len(candidates)),
    )
