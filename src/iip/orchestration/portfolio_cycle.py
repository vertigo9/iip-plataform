"""Portfolio-wide closed-loop orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class OrchestrationStage(StrEnum):
    SNAPSHOT = "snapshot"
    DATA = "data"
    INTELLIGENCE = "intelligence"
    DECISION = "decision"
    VALIDATION = "validation"
    REPORT = "report"


@dataclass(frozen=True)
class OrchestrationResult:
    ticker: str
    stage: OrchestrationStage
    success: bool
    payload: Any = None
    error: str | None = None


@dataclass(frozen=True)
class PortfolioCycleResult:
    cycle_id: str
    results: tuple[OrchestrationResult, ...]

    @property
    def success(self) -> bool:
        return bool(self.results) and all(item.success for item in self.results)


class PortfolioCycleOrchestrator:
    ORDER = (
        OrchestrationStage.SNAPSHOT,
        OrchestrationStage.DATA,
        OrchestrationStage.INTELLIGENCE,
        OrchestrationStage.DECISION,
        OrchestrationStage.VALIDATION,
        OrchestrationStage.REPORT,
    )

    def __init__(self, handlers: dict[OrchestrationStage, Callable[..., Any]]) -> None:
        self.handlers = dict(handlers)

    def run(self, cycle_id: str, ticker: str, **context) -> PortfolioCycleResult:
        results = []
        for stage in self.ORDER:
            handler = self.handlers.get(stage)
            if handler is None:
                results.append(
                    OrchestrationResult(
                        ticker.upper(),
                        stage,
                        False,
                        error=f"stage_not_registered:{stage.value}",
                    )
                )
                break
            try:
                value = handler(ticker.upper(), context, tuple(results))
                results.append(
                    OrchestrationResult(ticker.upper(), stage, True, payload=value)
                )
            except Exception as exc:
                results.append(
                    OrchestrationResult(
                        ticker.upper(),
                        stage,
                        False,
                        error=f"{type(exc).__name__}:{exc}",
                    )
                )
                break
        return PortfolioCycleResult(cycle_id, tuple(results))
