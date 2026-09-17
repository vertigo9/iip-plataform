"""Persistent CVM historical series for registered portfolio assets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from iip.atlas.models import AtlasDocument
from iip.sources.cvm_fii import build_target
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester


@dataclass(frozen=True)
class HistoricalObservation:
    period: str
    patrimonio_liquido: float | None
    valor_patrimonial_cotas: float | None
    dividend_yield_mes: float | None
    rentabilidade_patrimonial_mes: float | None
    valor_ativo: float | None
    total_numero_cotistas: float | None
    document_id: str
    document_hash: str
    discovered_year: int


@dataclass(frozen=True)
class HistoricalSeries:
    ticker: str
    cnpj: str
    provider: str
    observations: tuple[HistoricalObservation, ...]
    source_documents: tuple[dict[str, Any], ...]

    @property
    def nav_values(self) -> tuple[float, ...]:
        return tuple(
            item.valor_patrimonial_cotas
            for item in self.observations
            if item.valor_patrimonial_cotas is not None
        )

    @property
    def scale_breaks(self) -> tuple[tuple[str, str], ...]:
        breaks: list[tuple[str, str]] = []
        previous = None
        for item in self.observations:
            current = item.valor_patrimonial_cotas
            if previous is not None and current is not None:
                ratio = max(previous, current) / min(previous, current)
                if ratio >= 5.0:
                    breaks.append((item.period, f"ratio={ratio:.6f}"))
            if current is not None:
                previous = current
        return tuple(breaks)


class HistoricalSeriesStore:
    """Append-replace store for deterministic, auditable series snapshots."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def path_for(self, ticker: str) -> Path:
        return self.root / "02_Portfolio" / "Historical" / f"{ticker.upper()}.json"

    def save(self, series: HistoricalSeries) -> Path:
        path = self.path_for(series.ticker)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "type": "historical_series",
            "ticker": series.ticker,
            "cnpj": series.cnpj,
            "provider": series.provider,
            "observations": [asdict(item) for item in series.observations],
            "source_documents": list(series.source_documents),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, ticker: str) -> HistoricalSeries:
        payload = json.loads(self.path_for(ticker).read_text(encoding="utf-8"))
        return HistoricalSeries(
            ticker=payload["ticker"],
            cnpj=payload["cnpj"],
            provider=payload["provider"],
            observations=tuple(
                HistoricalObservation(**item) for item in payload["observations"]
            ),
            source_documents=tuple(payload["source_documents"]),
        )


def _digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def collect_cvm_fii_history(
    ticker: str,
    cnpj: str,
    years: range,
    *,
    store: HistoricalSeriesStore,
    harvester: CvmFiiHTTPHarvester | None = None,
) -> HistoricalSeries:
    """Collect and persist monthly CVM observations filtered by CNPJ."""
    normalized_cnpj = _digits(cnpj)
    if not normalized_cnpj:
        raise ValueError("cnpj must contain digits")

    transport = harvester or CvmFiiHTTPHarvester()
    observations: list[HistoricalObservation] = []
    source_documents: list[dict[str, Any]] = []
    seen_periods: set[str] = set()

    for year in years:
        report = transport.fetch(build_target(year))
        document = AtlasDocument.build(
            ticker=ticker,
            provider="cvm",
            role="regulatory",
            url=report.target.url,
            final_url=report.final_url or report.target.url,
            content_type=report.content_type or "application/zip",
            status_code=report.status_code,
            body=report.body,
            discovered_year=year,
            title=f"CVM FII Informe Mensal {year}",
        )
        source_documents.append(
            {
                "year": year,
                "document_id": document.document_id,
                "document_hash": document.content_hash,
                "source_url": document.final_url,
            }
        )
        for row in report.complemento:
            if _digits(row.cnpj_fundo_classe) != normalized_cnpj:
                continue
            if row.data_referencia in seen_periods:
                continue
            seen_periods.add(row.data_referencia)
            values = row.valores
            observations.append(
                HistoricalObservation(
                    period=row.data_referencia,
                    patrimonio_liquido=values.get("Patrimonio_Liquido"),
                    valor_patrimonial_cotas=values.get("Valor_Patrimonial_Cotas"),
                    dividend_yield_mes=values.get("Percentual_Dividend_Yield_Mes"),
                    rentabilidade_patrimonial_mes=values.get("Percentual_Rentabilidade_Patrimonial_Mes"),
                    valor_ativo=values.get("Valor_Ativo"),
                    total_numero_cotistas=values.get("Total_Numero_Cotistas"),
                    document_id=document.document_id,
                    document_hash=document.content_hash,
                    discovered_year=year,
                )
            )

    observations.sort(key=lambda item: item.period)
    series = HistoricalSeries(
        ticker=ticker.upper(),
        cnpj=normalized_cnpj,
        provider="cvm",
        observations=tuple(observations),
        source_documents=tuple(source_documents),
    )
    store.save(series)
    return series
