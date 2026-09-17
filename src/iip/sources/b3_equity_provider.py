"""Bolsai-backed document provider for equities and similar market assets."""

from __future__ import annotations

from iip.sources.b3_bolsai import build_target
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester
from iip.sources.provider import DocumentProvider
from iip.sources.registry import AssetRef


class BolsaiEquityProvider(DocumentProvider):
    """Build stock/ETF/BDR targets for the existing Bolsai transport."""

    provider_name = "b3"
    supported_asset_classes = frozenset({"equity", "etf", "bdr", "adr"})

    def supports(self, asset: AssetRef) -> bool:
        return asset.asset_class.strip().casefold() in self.supported_asset_classes

    def discover(self, asset: AssetRef, years: range):
        if not isinstance(years, range):
            raise TypeError("years must be a range")
        if not self.supports(asset):
            raise ValueError(f"{asset.ticker}: unsupported asset class")
        return (build_target(asset.ticker),)


def adapt_fundamentals(document):
    """Adapt the raw Bolsai response into an Atlas document."""
    from iip.atlas.models import AtlasDocument

    return AtlasDocument.build(
        ticker=document.target.ticker,
        provider=document.target.provider,
        role=document.target.role,
        url=document.target.url,
        final_url=document.final_url or document.target.url,
        content_type=document.content_type or "application/json",
        status_code=document.status_code,
        body=document.body,
        discovered_year=document.target.year,
        title=document.target.ticker,
    )


def build_bolsai_equity_binding(api_key: str, *, opener=None, timeout: float = 20.0):
    """Return provider and transport binding for configured Bolsai access."""
    from iip.atlas.ingestion import SourceTransportBinding

    provider = BolsaiEquityProvider()
    harvester = BolsaiHTTPHarvester(
        api_key=api_key,
        opener=opener,
        timeout=timeout,
    )
    return provider, SourceTransportBinding(
        provider.provider_name,
        harvester.fetch_many,
        adapt_fundamentals,
    )
