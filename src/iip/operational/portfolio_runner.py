"""Portfolio-wide operational data runner."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_gateway import AtlasGateway
from .discovery_chain import DiscoveryReport


@dataclass(frozen=True)
class AssetOperationalResult:
    ticker: str
    discovery: DiscoveryReport
    atlas_results: tuple[object, ...] = ()


class PortfolioOperationalRunner:
    def __init__(
        self, chain_factory, atlas_gateway: AtlasGateway | None = None
    ) -> None:
        self.chain_factory = chain_factory
        self.atlas_gateway = atlas_gateway

    def run_asset(self, ticker: str, years: range) -> AssetOperationalResult:
        report = self.chain_factory(ticker).discover(ticker, years)
        atlas_results = ()
        if self.atlas_gateway is not None:
            atlas_results = tuple(
                self.atlas_gateway.ingest(document) for document in report.documents
            )
        return AssetOperationalResult(ticker.upper(), report, atlas_results)
