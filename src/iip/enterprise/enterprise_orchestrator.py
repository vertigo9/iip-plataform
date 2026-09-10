"""Enterprise orchestration for the complete IIP lifecycle.

Legacy variant of the same concept as
``iip.system.pipeline.FullSystemPipeline`` — both model a
source-document-to-decision asset-onboarding pipeline with the same
staged-executor shape, but with incompatible handler call signatures
(this one calls ``handler(ticker, *args, **kwargs)``;
``FullSystemPipeline`` calls ``handler(ticker, context, trace)``), so
they cannot be merged without breaking one or the other's locked-in
tests. ``FullSystemPipeline`` is canonical: it also tracks a
``run_id``, threads a context dict through every stage, and
accumulates per-stage evidence via ``SystemArtifact.evidence_ids``,
none of which this module has. Use ``FullSystemPipeline`` for any new
work; this module is kept only because
``tests/test_enterprise_2001_3000.py`` still exercises it.
"""

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
