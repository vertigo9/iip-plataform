"""CVM FII provider that filters bulk reports by verified CNPJ."""

from __future__ import annotations

from dataclasses import replace

from iip.sources.cvm_fii import build_target
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester
from iip.sources.provider import DocumentProvider
from iip.sources.registry import AssetRef


def normalize_cnpj(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


class CvmFiiProvider(DocumentProvider):
    provider_name = "cvm"

    def supports(self, asset: AssetRef) -> bool:
        return (
            asset.asset_class.strip().casefold() == "fund"
            and bool(asset.asset_subtype.strip())
            and bool(getattr(asset, "cnpj", None))
        )

    def discover(self, asset: AssetRef, years: range):
        if not isinstance(years, range):
            raise TypeError("years must be a range")
        if not self.supports(asset):
            raise ValueError(f"{asset.ticker}: verified CNPJ required for CVM")
        cnpj = normalize_cnpj(asset.cnpj)
        return tuple(
            replace(build_target(year), ticker=asset.ticker, cnpj=cnpj)
            for year in years
        )


def adapt_fii_report(report) -> AtlasDocument:
    from iip.atlas.models import AtlasDocument

    target = report.target
    expected = normalize_cnpj(target.cnpj or "")
    if not expected:
        raise ValueError("CVM report target has no CNPJ")

    rows = (
        tuple(report.geral)
        + tuple(report.ativo_passivo)
        + tuple(report.complemento)
    )
    if not any(normalize_cnpj(row.cnpj_fundo_classe) == expected for row in rows):
        raise ValueError(f"{target.ticker}: CNPJ not found in CVM report")

    title = next(
        (
            row.nome_fundo_classe
            for row in report.geral
            if normalize_cnpj(row.cnpj_fundo_classe) == expected
            and row.nome_fundo_classe
        ),
        target.ticker,
    )
    return AtlasDocument.build(
        ticker=target.ticker,
        provider=target.provider,
        role=target.role,
        url=target.url,
        final_url=report.final_url or target.url,
        content_type=report.content_type or "application/zip",
        status_code=report.status_code,
        body=report.body,
        discovered_year=target.year,
        title=title,
    )


def build_cvm_fii_binding(*, opener=None, timeout: float = 60.0):
    from iip.atlas.ingestion import SourceTransportBinding

    provider = CvmFiiProvider()
    harvester = CvmFiiHTTPHarvester(opener=opener, timeout=timeout)
    return provider, SourceTransportBinding(
        provider.provider_name,
        harvester.fetch_many,
        adapt_fii_report,
    )
