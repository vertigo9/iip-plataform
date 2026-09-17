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
from .b3_equity_provider import BolsaiEquityProvider
from .cvm_fii_provider import CvmFiiProvider
from .b3_brapi_provider import BrapiMarketProvider
from .adapter_catalog import (
    ADAPTER_CATALOG,
    AdapterDescriptor,
    AdapterKind,
    AdapterReadiness,
    adapter_descriptor,
    ready_adapters,
)

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
    "BolsaiEquityProvider",
    "CvmFiiProvider",
    "BrapiMarketProvider",
    "ADAPTER_CATALOG",
    "AdapterDescriptor",
    "AdapterKind",
    "AdapterReadiness",
    "adapter_descriptor",
    "ready_adapters",
]
