"""Provider-agnostic source ingestion into Knowledge."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from iip.config import IIPSettings, get_settings
from iip.knowledge import KnowledgeBridge
from iip.sources import (
    AssetRef,
    ProviderRegistry,
    SourceRegistry,
    SourceRouter,
    XPAssetHTTPHarvester,
    XPAssetProvider,
)
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester
from iip.sources.b3_brapi_provider import BrapiMarketProvider, adapt_quotes
from iip.sources.b3_equity_provider import (
    BolsaiEquityProvider,
    adapt_fundamentals,
)
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester
from iip.sources.cvm_fii_provider import CvmFiiProvider, adapt_fii_report
from iip.sources.provider import DocumentProvider

from .adapter import AtlasDocumentAdapter
from .knowledge_adapter import AtlasKnowledgeAdapter
from .models import AtlasDocument


@dataclass(frozen=True)
class SourceTransportBinding:
    """Transport and normalization contract for one source provider."""

    provider: str
    fetch_many: Callable[[tuple[Any, ...]], tuple[Any, ...]]
    adapt: Callable[[Any], AtlasDocument]


@dataclass(frozen=True)
class IngestionResult:
    ticker: str
    provider: str | None
    documents: tuple[AtlasDocument, ...] = ()
    persisted: tuple[Any, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return bool(self.documents) and not self.errors


class SourceIngestionService:
    """Route, fetch, normalize and persist documents for any asset class."""

    def __init__(
        self,
        *,
        router: SourceRouter,
        providers: Mapping[str, DocumentProvider],
        transports: Mapping[str, SourceTransportBinding],
        knowledge_adapter: AtlasKnowledgeAdapter,
    ) -> None:
        self.router = router
        self.providers = {key.casefold(): value for key, value in providers.items()}
        self.transports = {key.casefold(): value for key, value in transports.items()}
        self.knowledge_adapter = knowledge_adapter

    def ingest(self, asset: AssetRef, years: range) -> IngestionResult:
        errors: list[str] = []
        routes = self.router.routes_for(asset)
        if not routes:
            return IngestionResult(
                asset.ticker,
                None,
                errors=("no_registered_source_route",),
            )

        for route in routes:
            provider_name = route.source.provider.casefold()
            provider = self.providers.get(provider_name, route.provider)
            binding = self.transports.get(provider_name)
            if binding is None:
                errors.append(f"{provider_name}:transport_not_registered")
                continue

            try:
                targets = tuple(provider.discover(asset, years))
                if not targets:
                    errors.append(f"{provider_name}:no_documents_discovered")
                    continue
                fetched = binding.fetch_many(targets)
                documents = tuple(binding.adapt(item) for item in fetched)
                if not documents:
                    errors.append(f"{provider_name}:no_documents_fetched")
                    continue
                persisted = tuple(
                    self.knowledge_adapter.persist(document) for document in documents
                )
                return IngestionResult(
                    asset.ticker, provider_name, documents, persisted
                )
            except Exception as exc:  # noqa: BLE001 - isolate one source route
                errors.append(f"{provider_name}:{type(exc).__name__}:{exc}")

        return IngestionResult(asset.ticker, None, errors=tuple(errors))

    def ingest_many(
        self, assets: Iterable[AssetRef], years: range
    ) -> tuple[IngestionResult, ...]:
        """Ingest a mixed portfolio while isolating each asset's failures."""
        return tuple(self.ingest(asset, years) for asset in assets)


def build_source_ingestion(
    vault: str,
    *,
    providers: Iterable[DocumentProvider],
    transports: Iterable[SourceTransportBinding],
) -> SourceIngestionService:
    """Compose any registered providers without provider-specific branching."""
    source_registry = SourceRegistry()
    provider_registry = ProviderRegistry()
    provider_items = tuple(providers)
    transport_items = tuple(transports)
    for provider in provider_items:
        provider_registry.register(provider)
    transport_map = {binding.provider: binding for binding in transport_items}
    provider_map = {provider.provider_name: provider for provider in provider_items}
    return SourceIngestionService(
        router=SourceRouter(
            source_registry=source_registry,
            provider_registry=provider_registry,
        ),
        providers=provider_map,
        transports=transport_map,
        knowledge_adapter=AtlasKnowledgeAdapter(KnowledgeBridge(vault)),
    )


def build_xp_asset_ingestion(
    vault: str,
    *,
    opener: Callable[..., object] | None = None,
    timeout: float = 20.0,
) -> SourceIngestionService:
    """Build the first concrete binding without constraining future providers."""
    provider = XPAssetProvider()
    harvester = XPAssetHTTPHarvester(opener=opener, timeout=timeout)
    document_adapter = AtlasDocumentAdapter()
    return build_source_ingestion(
        vault,
        providers=(provider,),
        transports=(
            SourceTransportBinding(
                provider.provider_name,
                harvester.fetch_many,
                document_adapter.from_fetched,
            )
        ),
    )


def build_configured_portfolio_ingestion(
    vault: str,
    *,
    settings: IIPSettings | None = None,
    opener: Callable[..., object] | None = None,
    timeout: float = 20.0,
) -> SourceIngestionService:
    """Build the enabled document providers from runtime configuration."""
    current = settings or get_settings()
    providers: list[DocumentProvider] = [XPAssetProvider()]
    transports: list[SourceTransportBinding] = []

    xp_provider = providers[0]
    xp_harvester = XPAssetHTTPHarvester(opener=opener, timeout=timeout)
    transports.append(
        SourceTransportBinding(
            xp_provider.provider_name,
            xp_harvester.fetch_many,
            AtlasDocumentAdapter().from_fetched,
        )
    )

    cvm_provider = CvmFiiProvider()
    cvm_harvester = CvmFiiHTTPHarvester(opener=opener, timeout=timeout)
    providers.append(cvm_provider)
    transports.append(
        SourceTransportBinding(
            cvm_provider.provider_name,
            lambda targets: tuple(cvm_harvester.fetch(target) for target in targets),
            adapt_fii_report,
        )
    )

    bolsai_key = current.bolsai_api_key
    bolsai_value = bolsai_key.get_secret_value() if bolsai_key is not None else None
    if bolsai_value:
        market_provider = BolsaiEquityProvider()
        market_harvester = BolsaiHTTPHarvester(
            api_key=bolsai_value,
            opener=opener,
            timeout=timeout,
        )
        providers.append(market_provider)
        transports.append(
            SourceTransportBinding(
                market_provider.provider_name,
                market_harvester.fetch_many,
                adapt_fundamentals,
            )
        )

    brapi_key = current.brapi_token
    brapi_value = brapi_key.get_secret_value() if brapi_key is not None else None
    if brapi_value:
        brapi_provider = BrapiMarketProvider()
        brapi_harvester = BrapiHTTPHarvester(
            token=brapi_value,
            opener=opener,
            timeout=timeout,
        )
        providers.append(brapi_provider)
        transports.append(
            SourceTransportBinding(
                brapi_provider.provider_name,
                brapi_harvester.fetch_many,
                adapt_quotes,
            )
        )
    return build_source_ingestion(
        vault,
        providers=providers,
        transports=transports,
    )
