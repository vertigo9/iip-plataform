"""Deterministic multi-provider discovery chain."""

from __future__ import annotations

from dataclasses import dataclass

from .normalization import NormalizedDocument, normalize_many
from .provider_adapter import AdapterExecutionStatus, AdapterResult, ProviderAdapter


@dataclass(frozen=True)
class DiscoveryReport:
    ticker: str
    attempts: tuple[AdapterResult, ...]
    documents: tuple[NormalizedDocument, ...]


class DiscoveryChain:
    def __init__(self, adapters: tuple[ProviderAdapter, ...]) -> None:
        self.adapters = adapters

    def discover(self, ticker: str, years: range) -> DiscoveryReport:
        attempts: list[AdapterResult] = []
        for adapter in self.adapters:
            result = adapter.discover(ticker, years)
            attempts.append(result)

            if result.status == AdapterExecutionStatus.READY and result.documents:
                docs = normalize_many(result.documents)
                return DiscoveryReport(ticker.upper(), tuple(attempts), docs)

        return DiscoveryReport(ticker.upper(), tuple(attempts), ())
