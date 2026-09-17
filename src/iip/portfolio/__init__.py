"""Portfolio registry and orchestration API."""

from .registry import (
    PORTFOLIO_ASSETS,
    ClassificationProvenance,
    PortfolioAsset,
    assets_by_class,
    get_asset,
)
from .source_policy import AssetSourcePolicy, PortfolioSourcePolicyResolver
from .source_router import PortfolioSourceRouter, RoutedPortfolioAsset
from .e2e import AssetE2EResult, AssetE2ERunner, E2EStep
from .historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
    collect_cvm_fii_history,
)

try:
    from .capabilities import Capability, ProviderCapabilities
except ImportError:
    Capability = None
    ProviderCapabilities = None

try:
    from .health_router import HealthAwareProviderSelector, ProviderHealthDecision
except ImportError:
    HealthAwareProviderSelector = None
    ProviderHealthDecision = None

try:
    from .incremental import IncrementalDocument, IncrementalTracker
except ImportError:
    IncrementalDocument = None
    IncrementalTracker = None

try:
    from .pipeline import (
        IntegratedPortfolioPipeline,
        PortfolioEvidenceBatchResult,
        PortfolioPipelineResult,
        ingest_registered_assets,
    )
except ImportError:
    IntegratedPortfolioPipeline = None
    PortfolioEvidenceBatchResult = None
    PortfolioPipelineResult = None
    ingest_registered_assets = None

__all__ = [
    "PORTFOLIO_ASSETS",
    "AssetSourcePolicy",
    "AssetE2EResult",
    "AssetE2ERunner",
    "Capability",
    "ClassificationProvenance",
    "HealthAwareProviderSelector",
    "IncrementalDocument",
    "IncrementalTracker",
    "E2EStep",
    "HistoricalObservation",
    "HistoricalSeries",
    "HistoricalSeriesStore",
    "collect_cvm_fii_history",
    "IntegratedPortfolioPipeline",
    "PortfolioEvidenceBatchResult",
    "PortfolioAsset",
    "PortfolioPipelineResult",
    "PortfolioSourcePolicyResolver",
    "PortfolioSourceRouter",
    "ProviderCapabilities",
    "ProviderHealthDecision",
    "RoutedPortfolioAsset",
    "assets_by_class",
    "get_asset",
    "ingest_registered_assets",
]
