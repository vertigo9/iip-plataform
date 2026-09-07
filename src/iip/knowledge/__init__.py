"""Persistent knowledge and decision layer for IIP."""

from .audit import DecisionAuditor
from .bridge import KnowledgeBridge
from .context import ContextAssembler, KnowledgeContext
from .models import (
    Decision,
    DecisionChange,
    Evidence,
    Exposure,
    PortfolioSnapshot,
    Position,
    Verdict,
)
from .projection import AssetNoteProjection, AssetNoteProjector
from .redundancy import find_redundant_exposures
from .repository import ObsidianRepository
from .vault import (
    AssetVaultLocation,
    AssetVaultLocator,
    normalize_asset_class,
    normalize_ticker,
)

__all__ = [
    "AssetNoteProjection",
    "AssetNoteProjector",
    "AssetVaultLocation",
    "AssetVaultLocator",
    "ContextAssembler",
    "Decision",
    "DecisionAuditor",
    "DecisionChange",
    "Evidence",
    "Exposure",
    "KnowledgeBridge",
    "KnowledgeContext",
    "ObsidianRepository",
    "PortfolioSnapshot",
    "Position",
    "ProjectionFingerprint",
    "ProjectionStatus",
    "ProjectionSyncEngine",
    "ProjectionSyncResult",
    "Verdict",
    "find_redundant_exposures",
    "normalize_asset_class",
    "normalize_ticker",
]
from .sync import (
    ProjectionFingerprint,
    ProjectionStatus,
    ProjectionSyncEngine,
    ProjectionSyncResult,
)
