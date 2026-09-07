"""Normalized provider adapter contract for real-source implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class AdapterExecutionStatus(StrEnum):
    READY = "ready"
    MAPPED = "mapped"
    FAILED = "failed"


@dataclass(frozen=True)
class RawDocument:
    document_id: str
    ticker: str
    title: str
    url: str
    category: str | None = None
    year: int | None = None
    content: bytes | None = None
    provider: str | None = None


@dataclass(frozen=True)
class AdapterResult:
    provider: str
    status: AdapterExecutionStatus
    documents: tuple[RawDocument, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class ProviderAdapter:
    provider: str
    source_url: str | None
    discover_fn: Callable[..., tuple[RawDocument, ...]] | None = None

    def discover(self, ticker: str, years: range) -> AdapterResult:
        if self.discover_fn is None:
            return AdapterResult(
                self.provider,
                AdapterExecutionStatus.MAPPED,
                error="discovery_not_implemented",
            )
        try:
            docs = self.discover_fn(ticker, years)
            return AdapterResult(
                self.provider,
                AdapterExecutionStatus.READY,
                tuple(docs),
            )
        except Exception as exc:
            return AdapterResult(
                self.provider,
                AdapterExecutionStatus.FAILED,
                error=f"{type(exc).__name__}:{exc}",
            )
