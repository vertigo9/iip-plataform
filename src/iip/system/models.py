"""Full-system execution contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SystemStage(StrEnum):
    SOURCE = "source"
    DISCOVERY = "discovery"
    ATLAS = "atlas"
    KNOWLEDGE = "knowledge"
    INTELLIGENCE = "intelligence"
    DECISION = "decision"
    VALIDATION = "validation"
    EXPORT = "export"


@dataclass(frozen=True)
class SystemArtifact:
    ticker: str
    stage: SystemStage
    payload: Any
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SystemTrace:
    run_id: str
    ticker: str
    artifacts: tuple[SystemArtifact, ...] = ()

    def add(self, artifact: SystemArtifact) -> SystemTrace:
        return SystemTrace(self.run_id, self.ticker, self.artifacts + (artifact,))


@dataclass(frozen=True)
class SystemResult:
    run_id: str
    ticker: str
    success: bool
    trace: SystemTrace
    error: str | None = None
