"""Integrated portfolio -> source -> router -> Atlas orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from iip.portfolio.registry import PORTFOLIO_ASSETS, PortfolioAsset
from iip.portfolio.source_router import PortfolioSourceRouter


@dataclass(frozen=True)
class PortfolioPipelineResult:
    asset: PortfolioAsset
    routed: object
    discovered: tuple[object, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioEvidenceBatchResult:
    """Document-ingestion results aligned with the real portfolio registry."""

    results: tuple[Any, ...]

    @property
    def succeeded(self) -> tuple[Any, ...]:
        return tuple(result for result in self.results if result.succeeded)

    @property
    def failed(self) -> tuple[Any, ...]:
        return tuple(result for result in self.results if not result.succeeded)


def ingest_registered_assets(
    ingestion_service: Any,
    years: range,
    assets: tuple[PortfolioAsset, ...] = PORTFOLIO_ASSETS,
) -> PortfolioEvidenceBatchResult:
    """Run the universal ingestion service against registered portfolio assets."""
    asset_refs = tuple(PortfolioSourceRouter.asset_ref(asset) for asset in assets)
    return PortfolioEvidenceBatchResult(
        ingestion_service.ingest_many(asset_refs, years)
    )


class IntegratedPortfolioPipeline:
    """Thin orchestration layer over the already-tested IIP components."""

    def __init__(
        self,
        *,
        source_router: PortfolioSourceRouter,
        atlas_pipeline_factory,
    ) -> None:
        self.source_router = source_router
        self.atlas_pipeline_factory = atlas_pipeline_factory

    def run(self, asset: PortfolioAsset, years: range) -> PortfolioPipelineResult:
        routed = self.source_router.route(asset)
        if routed.primary is None:
            return PortfolioPipelineResult(
                asset=asset,
                routed=routed,
                discovered=(),
                errors=("no_route",),
            )

        documents: list[object] = []
        errors: list[str] = []

        for route in routed.routes:
            try:
                atlas_pipeline = self.atlas_pipeline_factory(route.provider)
                report = atlas_pipeline.ingest(
                    self.source_router._asset_ref(asset), years
                )
                documents.extend(report.documents)
                if documents:
                    break
            # isola falha de uma rota, permite tentar a proxima
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{route.source.provider}:{type(exc).__name__}")

        return PortfolioPipelineResult(
            asset=asset,
            routed=routed,
            discovered=tuple(documents),
            errors=tuple(errors),
        )
