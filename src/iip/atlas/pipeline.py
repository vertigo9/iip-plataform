"""End-to-end source -> Atlas ingestion pipeline.

D-OBSIDIAN-06.2-05
"""

from __future__ import annotations

from dataclasses import dataclass

from iip.sources.harvester import FetchedDocument, XPAssetHTTPHarvester
from iip.sources.registry import AssetRef
from iip.sources.xp_asset import DocumentTarget, XPAssetProvider

from .adapter import AtlasDocumentAdapter
from .models import AtlasDocument


@dataclass(frozen=True)
class AtlasIngestionReport:
    """Result of one deterministic discovery/harvest/normalize run."""

    targets: tuple[DocumentTarget, ...]
    fetched: tuple[FetchedDocument, ...]
    documents: tuple[AtlasDocument, ...]


class XPAssetAtlasPipeline:
    """Connect XP Asset discovery and transport to Atlas normalization."""

    def __init__(
        self,
        *,
        provider: XPAssetProvider | None = None,
        harvester: XPAssetHTTPHarvester | None = None,
        adapter: AtlasDocumentAdapter | None = None,
    ) -> None:
        self.provider = provider or XPAssetProvider()
        self.harvester = harvester or XPAssetHTTPHarvester()
        self.adapter = adapter or AtlasDocumentAdapter()

    def ingest(self, asset: AssetRef, years: range) -> AtlasIngestionReport:
        """Discover targets, fetch them, then normalize them into Atlas."""
        targets = self.provider.discover(asset, years)
        fetched = self.harvester.fetch_many(targets)
        documents = tuple(self.adapter.from_fetched(item) for item in fetched)
        return AtlasIngestionReport(
            targets=targets,
            fetched=fetched,
            documents=documents,
        )
