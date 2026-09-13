"""Portfolio-wide operational data runner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from iip.data.quotes import YFinanceGateway
from iip.decision.decision_engine import (
    ingest_equity_harvest,
    ingest_etf_harvest,
    ingest_fii_harvest,
    ingest_fixed_income_harvest,
)
from iip.intelligence.thesis_rag import ThesisRAGAnalyzer

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
        "REIT": ingest_fii_harvest,
        "EQUITY": ingest_equity_harvest,
        "STOCKS": ingest_equity_harvest,
        "BDR": ingest_equity_harvest,
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


from iip.obsidian.asset_updater import update_asset_note

def run_portfolio_cycle(
    assets_manifest: list[dict[str, Any]],
    vault_path: Path | str | None = None,
) -> dict[str, Any]:
    """Executa o ciclo completo da carteira com enriquecimento spot, cambial, RAG e sync no Obsidian."""
    results = {"processed": 0, "errors": 0, "observations": []}
    quote_gateway = YFinanceGateway()
    rag_analyzer = ThesisRAGAnalyzer()

    for item in assets_manifest:
        ticker = item.get("ticker", "UNKNOWN")
        asset_class = item.get("asset_class", "EQUITY")
        fetched_data = item.get("fetched_data")
        raw_metrics = item.get("metrics", {})
        report_text = item.get("report_text", "")

        try:
            # 1. Preço Spot & Normalização Cambial
            spot_data = quote_gateway.fetch_spot_price(ticker)
            raw_metrics["SPOT_PRICE"] = float(spot_data["spot_price"])

            if spot_data["currency"] != "BRL":
                fx_rate = quote_gateway.fetch_exchange_rate(spot_data["currency"], "BRL")
                raw_metrics["FX_RATE"] = float(fx_rate)
                raw_metrics["SPOT_PRICE_BRL"] = float(spot_data["spot_price"] * fx_rate)
            else:
                raw_metrics["FX_RATE"] = 1.0
                raw_metrics["SPOT_PRICE_BRL"] = float(spot_data["spot_price"])

            # 2. Processamento RAG
            if report_text:
                rag_result = rag_analyzer.analyze_report(ticker, report_text)
                raw_metrics["RAG_CONFIDENCE"] = float(rag_result.confidence)

            # 3. Filtragem Estrita de Métricas Numéricas para o DecisionEngine
            engine_metrics = {}
            for k, v in raw_metrics.items():
                try:
                    engine_metrics[k] = float(v)
                except (ValueError, TypeError):
                    pass

            # 4. Despacho ao Decision Engine
            obs = dispatch_harvest_to_engine(fetched_data, asset_class, engine_metrics)
            results["observations"].extend(obs)
            results["processed"] += 1

            # 5. Sync de Nota Individual no Obsidian Vault
            if vault_path:
                update_asset_note(
                    vault_path=vault_path,
                    ticker=ticker,
                    asset_class=asset_class,
                    metrics=raw_metrics,
                    verdict_data={
                        "score": raw_metrics.get("SCORE", "N/A"),
                        "verdict": raw_metrics.get("VERDICT", "AGUARDAR"),
                        "confidence": raw_metrics.get("RAG_CONFIDENCE", 0.0),
                    },
                )
        except Exception as exc:
            logger.error("Falha ao processar ativo %s: %s", ticker, exc)
            results["errors"] += 1

    return results