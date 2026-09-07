"""IIP source registry, providers, health and routing API."""

from .discovery import MultiProviderDiscovery, ProviderDiscovery
from .harvester import FetchedDocument, XPAssetHTTPHarvester
from .health import SourceHealth
from .health_registry import SourceHealthRegistry
from .provider import DocumentProvider
from .provider_registry import ProviderRegistry
from .registry import AssetRef, SourceRef, SourceRegistry
from .router import SourceRoute, SourceRouter
from .xp_asset import DocumentTarget, XPAssetProvider

__all__ = [
    "AssetRef",
    "DocumentProvider",
    "DocumentTarget",
    "FetchedDocument",
    "MultiProviderDiscovery",
    "ProviderDiscovery",
    "ProviderRegistry",
    "SourceHealth",
    "SourceHealthRegistry",
    "SourceRef",
    "SourceRegistry",
    "SourceRoute",
    "SourceRouter",
    "XPAssetHTTPHarvester",
    "XPAssetProvider",
]
