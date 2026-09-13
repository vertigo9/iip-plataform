"""Portfolio-wide operational data runner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from iip.decision.decision_engine import (
    ingest_equity_harvest,
    ingest_etf_harvest,
    ingest_fii_harvest,
    ingest_fixed_income_harvest,
)

from .atlas_gateway import AtlasGateway
from .discovery_chain import DiscoveryReport

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetOperationalResult:
    ticker: str
    discovery: DiscoveryReport
    atlas_results: tuple[object, ...] = ()


class PortfolioOperationalRunner:
    def __init__(
        self, chain_factory, atlas_gateway: AtlasGateway | None = None
    ) -> None:
        self.chain_factory = chain_factory
        self.atlas_gateway = atlas_gateway

    def run_asset(self, ticker: str, years: range) -> AssetOperationalResult:
        report = self.chain_factory(ticker).discover(ticker, years)
        atlas_results = ()
        if self.atlas_gateway is not None:
            atlas_results = tuple(
                self.atlas_gateway.ingest(document) for document in report.documents
            )
        return AssetOperationalResult(ticker.upper(), report, atlas_results)


def dispatch_harvest_to_engine(
    fetched_data: Any,
    asset_class: str,
    metrics_payload: dict[str, float],
) -> list[Any]:
    """Despacha a carga colhida para a rota especializada do DecisionEngine com base na classe do ativo."""
    class_normalized = str(asset_class or "").upper().strip()

    class_map = {
        "FII": ingest_fii_harvest,
        "EQUITY": ingest_equity_harvest,
        "STOCKS": ingest_equity_harvest,
        "ACAO": ingest_equity_harvest,
        "ACOES": ingest_equity_harvest,
        "ETF": ingest_etf_harvest,
        "FIXED_INCOME": ingest_fixed_income_harvest,
        "RENDA_FIXA": ingest_fixed_income_harvest,
        "FIAGRO": ingest_fixed_income_harvest,
        "FI_INFRA": ingest_fixed_income_harvest,
    }

    handler = class_map.get(class_normalized, ingest_fixed_income_harvest)
    logger.info("Despachando ativo de classe '%s' via handler '%s'", class_normalized, handler.__name__)
    return handler(fetched_data, metrics_payload)


def run_portfolio_cycle(assets_manifest: list[dict[str, Any]]) -> dict[str, Any]:
    """Executa o ciclo completo da carteira para múltiplos ativos."""
    results = {"processed": 0, "errors": 0, "observations": []}

    for item in assets_manifest:
        ticker = item.get("ticker", "UNKNOWN")
        asset_class = item.get("asset_class", "EQUITY")
        fetched_data = item.get("fetched_data")
        metrics = item.get("metrics", {})

        try:
            obs = dispatch_harvest_to_engine(fetched_data, asset_class, metrics)
            results["observations"].extend(obs)
            results["processed"] += 1
        except Exception as exc:
            logger.error("Falha ao processar ativo %s: %s", ticker, exc)
            results["errors"] += 1

    return results