"""Cycle-level reporting summary."""

from __future__ import annotations

from dataclasses import dataclass

from .portfolio_cycle import PortfolioCycleResult


@dataclass(frozen=True)
class CycleSummary:
    cycle_id: str
    assets_processed: int
    success: bool
    failed_assets: int


def summarize(cycle_id: str, runs: tuple[PortfolioCycleResult, ...]) -> CycleSummary:
    return CycleSummary(
        cycle_id=cycle_id,
        assets_processed=len(runs),
        success=all(run.success for run in runs) if runs else False,
        failed_assets=sum(not run.success for run in runs),
    )
