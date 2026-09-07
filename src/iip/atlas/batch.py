"""Batch helpers for historical Atlas ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from iip.sources.registry import AssetRef

from .history import AtlasHistoryProcessor, HistoryBatch


@dataclass(frozen=True)
class HistoricalIngestionResult:
    """Normalized result of a historical Atlas pipeline run."""

    report: object
    history: HistoryBatch


class HistoricalAtlasIngestion:
    """Run the existing Atlas pipeline and normalize its document batch."""

    def __init__(self, atlas_pipeline, history_processor=None) -> None:
        self.atlas_pipeline = atlas_pipeline
        self.history_processor = history_processor or AtlasHistoryProcessor()

    def ingest(self, asset: AssetRef, years: range) -> HistoricalIngestionResult:
        report = self.atlas_pipeline.ingest(asset, years)
        history = self.history_processor.process(report.documents)
        return HistoricalIngestionResult(report=report, history=history)
