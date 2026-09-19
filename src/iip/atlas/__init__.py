"""Atlas ingestion contracts, adapters and Knowledge integration."""

from .adapter import AtlasDocumentAdapter
from .ingestion import (
    IngestionResult,
    SourceIngestionService,
    SourceTransportBinding,
    build_configured_portfolio_ingestion,
    build_source_ingestion,
    build_xp_asset_ingestion,
)
from .knowledge_adapter import AtlasKnowledgeAdapter
from .models import AtlasDocument
from .pipeline import AtlasIngestionReport, XPAssetAtlasPipeline

__all__ = [
    "AtlasDocument",
    "AtlasDocumentAdapter",
    "AtlasIngestionReport",
    "AtlasKnowledgeAdapter",
    "IngestionResult",
    "SourceIngestionService",
    "SourceTransportBinding",
    "build_source_ingestion",
    "build_configured_portfolio_ingestion",
    "build_xp_asset_ingestion",
    "XPAssetAtlasPipeline",
]
