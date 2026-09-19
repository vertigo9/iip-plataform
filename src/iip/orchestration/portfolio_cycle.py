"""Portfolio-wide closed-loop orchestration.

Distinct concept from ``iip.system.pipeline.FullSystemPipeline`` (the
canonical asset-onboarding pipeline) despite the same staged-executor
shape (Stage enum + ORDER tuple + injected handlers) — confirmed by
audit, not assumed from the shape alone. This one models a
**recurring cycle over an already-onboarded portfolio**: its stages
start at SNAPSHOT/DATA, skipping SOURCE/ATLAS/KNOWLEDGE entirely,
because it assumes the assets involved have already been through
onboarding and just need periodic re-evaluation (intelligence ->
decision -> validation -> report on current holdings).

Do not treat this as legacy or fold it into ``FullSystemPipeline`` —
they answer different questions ("bring this new asset's documents
all the way to a decision" vs. "re-run intelligence/decision/
validation over the portfolio I already have"). If a future portfolio
cycle needs to onboard a not-yet-known asset mid-cycle, the natural
integration point is to invoke ``FullSystemPipeline`` from within this
orchestrator's DATA stage handler — not to merge the two frameworks.
"""

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
            # isola falha do handler por estagio, nao derruba o ciclo inteiro
            except Exception as exc:  # noqa: BLE001
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
