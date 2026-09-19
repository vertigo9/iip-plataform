"""Full strategy E2E result."""

from __future__ import annotations

from dataclasses import dataclass

from .pipeline import StrategyPipelineInput, run


@dataclass(frozen=True)
class StrategyE2E:
    report: object
    success: bool


def execute(data: StrategyPipelineInput) -> StrategyE2E:
    try:
        report = run(data)
        valid = (
            report is not None
            and len(report.decisions) == len(data.assets)
            and report.income_plan.gap >= 0
        )
        return StrategyE2E(report, valid)
    # isola falha do pipeline e2e, retorna resultado negativo em vez de propagar
    except Exception:  # noqa: BLE001
        return StrategyE2E(None, False)
