"""XPML11 full ingestion pipeline: Source -> Atlas -> Knowledge -> Obsidian."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from iip.sources.registry import AssetRef


@dataclass(frozen=True)
class FullIngestionReport:
    """Complete result of one source-to-Knowledge/Obsidian run."""

    atlas_report: Any
    knowledge_results: tuple[Any, ...]


class XPAssetKnowledgePipeline:
    """Orchestrate the already-tested provider/harvester/Atlas/Knowledge layers.

    Existing components are injected instead of replaced. This keeps the
    D-OBSIDIAN-06.1/06.2 contracts intact and makes the orchestration layer
    easy to test offline.
    """

    def __init__(
        self,
        *,
        atlas_pipeline,
        knowledge_adapter,
    ) -> None:
        self.atlas_pipeline = atlas_pipeline
        self.knowledge_adapter = knowledge_adapter

    def ingest(self, asset: AssetRef, years: range) -> FullIngestionReport:
        """Run discovery, fetch, normalization and Knowledge persistence."""
        atlas_report = self.atlas_pipeline.ingest(asset, years)
        knowledge_results = self.knowledge_adapter.persist_many(atlas_report.documents)
        return FullIngestionReport(
            atlas_report=atlas_report,
            knowledge_results=knowledge_results,
        )
