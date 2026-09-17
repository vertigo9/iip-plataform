"""BrAPI quote provider for market validation."""

from __future__ import annotations

from iip.sources.b3_brapi import build_target
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester
from iip.sources.provider import DocumentProvider
from iip.sources.registry import AssetRef


class BrapiMarketProvider(DocumentProvider):
    provider_name = "b3_brapi"
    supported_asset_classes = frozenset({"equity", "etf", "bdr", "adr"})

    def supports(self, asset: AssetRef) -> bool:
        return asset.asset_class.strip().casefold() in self.supported_asset_classes

    def discover(self, asset: AssetRef, years: range):
        if not isinstance(years, range):
            raise TypeError("years must be a range")
        if not self.supports(asset):
            raise ValueError(f"{asset.ticker}: unsupported asset class")
        return (build_target((asset.ticker,)),)


def adapt_quotes(document):
    from iip.atlas.models import AtlasDocument

    target = document.target
    return AtlasDocument.build(
        ticker=target.symbols[0],
        provider="b3_brapi",
        role="market_validation",
        url=target.url,
        final_url=document.final_url or target.url,
        content_type=document.content_type or "application/json",
        status_code=document.status_code,
        body=document.body,
        discovered_year=getattr(target, "year", None),
        title=target.symbols[0],
    )


def build_brapi_market_binding(token: str, *, opener=None, timeout: float = 20.0):
    from iip.atlas.ingestion import SourceTransportBinding

    provider = BrapiMarketProvider()
    harvester = BrapiHTTPHarvester(token=token, opener=opener, timeout=timeout)
    return provider, SourceTransportBinding(
        provider.provider_name,
        harvester.fetch_many,
        adapt_quotes,
    )
