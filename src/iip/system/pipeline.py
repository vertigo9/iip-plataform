"""Full-system orchestration over explicit injected stage handlers.

Canonical central orchestration framework for the **asset-onboarding**
pipeline (source document -> decision), chosen after an audit found
three parallel generic staged-executors in this codebase with the same
shape (Stage enum + ORDER tuple + injected handler dict + stop-on-first-
failure): this one, ``iip.enterprise.orchestrator.EnterpriseOrchestrator``,
and ``iip.orchestration.portfolio_cycle.PortfolioCycleOrchestrator``.

This module and ``EnterpriseOrchestrator`` model the *same* concept
(SOURCE/DISCOVERY -> ATLAS -> KNOWLEDGE -> INTELLIGENCE -> DECISION ->
VALIDATION -> export/reporting) — true duplicates. This one is
canonical between the two: it is the more complete of the pair (tracks
``run_id``, threads a ``context`` dict through every stage, and
accumulates per-stage evidence via ``SystemArtifact.evidence_ids``).
``EnterpriseOrchestrator`` is documented as the legacy variant of this
same concept — do not delegate between them, their handler call
signatures are incompatible and each is locked in by its own test
suite.

``PortfolioCycleOrchestrator`` is NOT a duplicate of this one, despite
the superficial shape match — it models a different concept (a
recurring cycle over an *already onboarded* portfolio, starting from
SNAPSHOT/DATA rather than SOURCE/ATLAS/KNOWLEDGE) and is documented on
its own terms, not as legacy.

None of the three orchestrators is wired to real domain pipelines yet
(confirmed by audit — no non-test instantiation of any of them exists
in this codebase). Any future wiring of the real onboarding flow
(atlas ingestion, knowledge persistence, the Promotion Gate, decision
scoring, validation) into a generic staged executor should use this
one.
"""

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
            # isola falha de um estagio do pipeline, nao derruba a run inteira
            except Exception as exc:  # noqa: BLE001
                return SystemResult(
                    run_id,
                    ticker.upper(),
                    False,
                    trace,
                    error=f"{type(exc).__name__}:{exc}",
                )
        return SystemResult(run_id, ticker.upper(), True, trace)
