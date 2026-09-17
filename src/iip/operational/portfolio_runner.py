"""Portfolio-wide operational data runner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from iip.data.quotes import YFinanceGateway
from iip.intelligence.thesis_rag import ThesisRAGAnalyzer
from iip.obsidian.asset_updater import update_asset_note

from .atlas_gateway import AtlasGateway
from .discovery_chain import DiscoveryReport

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetOperationalResult:
    ticker: str
    discovery: DiscoveryReport
    atlas_results: tuple[object, ...] = ()
    knowledge_results: tuple[object, ...] = ()


class PortfolioOperationalRunner:
    def __init__(
        self,
        chain_factory,
        atlas_gateway: AtlasGateway | None = None,
        evidence_sink=None,
    ) -> None:
        self.chain_factory = chain_factory
        self.atlas_gateway = atlas_gateway
        self.evidence_sink = evidence_sink

    def run_asset(self, ticker: str, years: range) -> AssetOperationalResult:
        report = self.chain_factory(ticker).discover(ticker, years)
        atlas_results = ()
        knowledge_results = ()
        if self.atlas_gateway is not None:
            atlas_results_list = []
            knowledge_results_list = []
            for document in report.documents:
                atlas_result = self.atlas_gateway.ingest(document)
                atlas_results_list.append(atlas_result)
                if self.evidence_sink is not None and atlas_result.success:
                    knowledge_results_list.append(self.evidence_sink.persist(document))
            atlas_results = tuple(atlas_results_list)
            knowledge_results = tuple(knowledge_results_list)
        return AssetOperationalResult(
            ticker.upper(), report, atlas_results, knowledge_results
        )


def dispatch_harvest_to_engine(
    fetched_data: Any,
    asset_class: str,
    metrics_payload: dict[str, float],
) -> list[Any]:
    """Stub deliberado -- NÃO gera nenhum MetricObservationIdentity/
    HistoricalMetricEvidence a partir deste payload.

    Achado real (14/09/2026): YFinanceGateway e B3Gateway retornam dado
    inteiramente mockado -- ``fetch_spot_price`` sempre devolve 100.00
    pra qualquer ticker, ``fetch_exchange_rate`` sempre 5.50 fixo,
    ``fetch_dividends`` só olha o sufixo do ticker, e
    ``B3Gateway.fetch_user_positions`` ignora o CPF recebido e sempre
    retorna a mesma lista fixa de 3 posições. Nenhum desses tem
    chamada de rede real, então não há ``body``/``content_type``/
    ``final_url`` nenhum pra capturar -- não é uma lacuna de
    "transporte não fechado" (como era o caso do FII antes do
    TRACE 15.13), é ausência total de fonte real.

    As 4 funções antigas (``ingest_fii_harvest`` etc., removidas de
    ``decision_engine.py``) criavam evidência de métrica a partir
    desse dado mockado como se fosse real -- exatamente o tipo de
    proveniência fabricada que este projeto existe pra evitar. Este
    stub existe só pra manter o import/dispatch funcionando sem
    quebrar o restante do pipeline (RAG, sync com Obsidian) enquanto
    YFinanceGateway/B3Gateway não tiverem uma implementação real.

    Retorna sempre lista vazia. Loga um aviso explícito, uma vez por
    chamada, pra não esconder a limitação.
    """
    logger.warning(
        "dispatch_harvest_to_engine chamado para ticker de classe '%s' -- "
        "nenhuma evidência real é gerada aqui (YFinanceGateway/B3Gateway "
        "ainda são mock, sem chamada de rede real). Isso é esperado até "
        "esses gateways terem implementação real.",
        str(asset_class or "").upper().strip(),
    )
    return []


def run_portfolio_cycle(
    assets_manifest: list[dict[str, Any]],
    vault_path: Path | str | None = None,
) -> dict[str, Any]:
    """Executa o ciclo completo da carteira com enriquecimento spot, cambial, RAG e sync no Obsidian.

    Aviso honesto: hoje ``quote_gateway`` (YFinanceGateway) é mock fixo
    -- ``SPOT_PRICE``/``FX_RATE``/dividendos gerados aqui NÃO são dado
    de mercado real. Mantido funcionando (não removido) porque outras
    partes do ciclo (sync com Obsidian, RAG) ainda são úteis pra
    desenvolvimento/teste, mas nenhum desses valores deve ser tratado
    como decisão real até YFinanceGateway ter implementação real.
    """
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

            # 4. Despacho ao Decision Engine -- stub, ver docstring de
            # dispatch_harvest_to_engine: nao gera evidencia real hoje.
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
        except Exception as exc:  # noqa: BLE001 -- isolamento por ativo, uma falha nao trava os outros
            logger.error("Falha ao processar ativo %s: %s", ticker, exc)
            results["errors"] += 1

    return results
