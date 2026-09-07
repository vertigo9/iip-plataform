"""Provider capability contracts for multi-asset routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    DISCOVERY = "discovery"
    DOCUMENT_DOWNLOAD = "document_download"
    HISTORICAL = "historical"
    INCREMENTAL = "incremental"
    MARKET_DATA = "market_data"


@dataclass(frozen=True)
class ProviderCapabilities:
    provider: str
    capabilities: frozenset[Capability]

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities
