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
    from .pipeline import IntegratedPortfolioPipeline, PortfolioPipelineResult
except ImportError:
    IntegratedPortfolioPipeline = None
    PortfolioPipelineResult = None

__all__ = [
    "PORTFOLIO_ASSETS",
    "AssetSourcePolicy",
    "Capability",
    "ClassificationProvenance",
    "HealthAwareProviderSelector",
    "IncrementalDocument",
    "IncrementalTracker",
    "IntegratedPortfolioPipeline",
    "PortfolioAsset",
    "PortfolioPipelineResult",
    "PortfolioSourcePolicyResolver",
    "PortfolioSourceRouter",
    "ProviderCapabilities",
    "ProviderHealthDecision",
    "RoutedPortfolioAsset",
    "assets_by_class",
    "get_asset",
]
