"""Enterprise orchestration for the complete IIP lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Stage(StrEnum):
    DISCOVERY = "discovery"
    ATLAS = "atlas"
    KNOWLEDGE = "knowledge"
    INTELLIGENCE = "intelligence"
    DECISION = "decision"
    VALIDATION = "validation"
    REPORTING = "reporting"


@dataclass(frozen=True)
class StageResult:
    stage: Stage
    success: bool
    value: Any = None
    error: str | None = None


@dataclass(frozen=True)
class EnterpriseRun:
    ticker: str
    results: tuple[StageResult, ...]

    @property
    def success(self) -> bool:
        return bool(self.results) and all(item.success for item in self.results)


class EnterpriseOrchestrator:
    """Run explicit stages in deterministic order.

    Each stage handler is injected by the caller. No hidden network calls,
    provider guessing, or automatic live execution is introduced.
    """

    ORDER = (
        Stage.DISCOVERY,
        Stage.ATLAS,
        Stage.KNOWLEDGE,
        Stage.INTELLIGENCE,
        Stage.DECISION,
        Stage.VALIDATION,
        Stage.REPORTING,
    )

    def __init__(self, handlers: dict[Stage, Callable[..., Any]]) -> None:
        self.handlers = dict(handlers)

    def run(self, ticker: str, *args, **kwargs) -> EnterpriseRun:
        results = []
        for stage in self.ORDER:
            handler = self.handlers.get(stage)
            if handler is None:
                results.append(StageResult(stage, False, error="stage_not_registered"))
                break
            try:
                value = handler(ticker, *args, **kwargs)
                results.append(StageResult(stage, True, value=value))
            except Exception as exc:
                results.append(
                    StageResult(stage, False, error=f"{type(exc).__name__}:{exc}")
                )
                break
        return EnterpriseRun(ticker.upper(), tuple(results))
