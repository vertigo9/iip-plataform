"""Cross-layer contracts for the accelerated IIP platform block."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceKind(StrEnum):
    DOCUMENT = "document"
    MARKET_DATA = "market_data"
    REGULATORY = "regulatory"
    INSTITUTIONAL = "institutional"
    INTERNAL = "internal"


class ExecutionState(StrEnum):
    READY = "ready"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: EvidenceKind
    provider: str
    source: str
    content_hash: str | None = None
    observed_at: str | None = None


@dataclass(frozen=True)
class ProviderRun:
    provider: str
    state: ExecutionState
    evidence: tuple[Evidence, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class AssetRun:
    ticker: str
    state: ExecutionState
    provider_runs: tuple[ProviderRun, ...]
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class PortfolioRun:
    assets: tuple[AssetRun, ...]

    @property
    def succeeded(self) -> int:
        return sum(asset.state == ExecutionState.READY for asset in self.assets)

    @property
    def failed(self) -> int:
        return sum(asset.state == ExecutionState.FAILED for asset in self.assets)
