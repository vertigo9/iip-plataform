"""Full-system orchestration over explicit injected stage handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import SystemArtifact, SystemResult, SystemStage, SystemTrace


@dataclass(frozen=True)
class StageHandler:
    stage: SystemStage
    handler: Callable[..., Any]


class FullSystemPipeline:
    ORDER = (
        SystemStage.SOURCE,
        SystemStage.DISCOVERY,
        SystemStage.ATLAS,
        SystemStage.KNOWLEDGE,
        SystemStage.INTELLIGENCE,
        SystemStage.DECISION,
        SystemStage.VALIDATION,
        SystemStage.EXPORT,
    )

    def __init__(self, handlers: tuple[StageHandler, ...]) -> None:
        self.handlers = {item.stage: item.handler for item in handlers}

    def run(self, run_id: str, ticker: str, **context) -> SystemResult:
        trace = SystemTrace(run_id, ticker.upper())
        for stage in self.ORDER:
            handler = self.handlers.get(stage)
            if handler is None:
                return SystemResult(
                    run_id,
                    ticker.upper(),
                    False,
                    trace,
                    error=f"stage_not_registered:{stage.value}",
                )
            try:
                value = handler(ticker.upper(), context, trace)
                evidence_ids = tuple(getattr(value, "evidence_ids", ()) or ())
                trace = trace.add(
                    SystemArtifact(ticker.upper(), stage, value, evidence_ids)
                )
            except Exception as exc:
                return SystemResult(
                    run_id,
                    ticker.upper(),
                    False,
                    trace,
                    error=f"{type(exc).__name__}:{exc}",
                )
        return SystemResult(run_id, ticker.upper(), True, trace)
