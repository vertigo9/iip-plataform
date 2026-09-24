"""Persistent CVM historical series for registered portfolio assets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from iip.atlas.models import AtlasDocument
from iip.sources.cvm_fii import build_target
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester

# A ratio at/above this factor between two consecutive monthly NAV-per-quota
# values is treated as a scale break -- almost certainly a quota split or
# grouping (desdobramento/grupamento), never organic monthly price movement.
_SCALE_BREAK_RATIO = 5.0


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
    adjustments: tuple[dict[str, Any], ...] = ()

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
                if ratio >= _SCALE_BREAK_RATIO:
                    breaks.append((item.period, f"ratio={ratio:.6f}"))
            if current is not None:
                previous = current
        return tuple(breaks)


def normalize_quota_splits(series: HistoricalSeries) -> HistoricalSeries:
    """Rescale NAV-per-quota values before each detected break onto the
    current quota basis, so the whole series is comparable for volatility
    and return calculations.

    Only ``valor_patrimonial_cotas`` is per-quota; ``patrimonio_liquido``,
    ``valor_ativo`` and ``total_numero_cotistas`` are fund/shareholder
    totals unaffected by a split and are left untouched.

    Call this only after confirming a ``scale_breaks`` entry is a genuine
    quota split/grouping -- e.g. ``patrimonio_liquido`` and
    ``total_numero_cotistas`` stay continuous across the break, ruling out
    a data error. This function rescales unconditionally once called; it
    does not re-verify that the break is legitimate.
    """
    observations = list(series.observations)
    breaks: list[tuple[int, float]] = []
    previous_value: float | None = None
    for index, item in enumerate(observations):
        current_value = item.valor_patrimonial_cotas
        if previous_value is not None and current_value is not None:
            ratio = max(previous_value, current_value) / min(
                previous_value, current_value
            )
            if ratio >= _SCALE_BREAK_RATIO:
                breaks.append((index, previous_value / current_value))
        if current_value is not None:
            previous_value = current_value

    adjustments = list(series.adjustments)
    for break_index, factor in breaks:
        for i in range(break_index):
            item = observations[i]
            if item.valor_patrimonial_cotas is not None:
                observations[i] = replace(
                    item, valor_patrimonial_cotas=item.valor_patrimonial_cotas / factor
                )
        adjustments.append(
            {
                "period": observations[break_index].period,
                "field": "valor_patrimonial_cotas",
                "factor": factor,
                "reason": "quota split/grouping confirmed via patrimonio_liquido continuity",
            }
        )

    return replace(
        series, observations=tuple(observations), adjustments=tuple(adjustments)
    )


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
            "adjustments": list(series.adjustments),
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
            adjustments=tuple(payload.get("adjustments", ())),
        )


def _digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def _persist_atlas_evidence(bridge: Any, document: AtlasDocument) -> None:
    """Persist a fetched document as real Atlas evidence.

    Calls ``bridge.persist_evidence`` directly rather than
    ``AtlasKnowledgeAdapter.persist()``, which also calls
    ``sync_evidence_projection`` -- kept minimal on purpose here (no
    note-section sync), not to dodge a bug: ``sync_evidence_projection``
    used to hardcode asset_class "FII" for the mirrored note section
    (misfiling non-FII tickers' sources section into the FIIs folder),
    fixed in the PR of 24/09/2026 (it now resolves the real class via
    the Registry). The evidence store write itself
    (``04_Evidence/<id>.md``) was always asset-class-agnostic and
    unaffected either way.
    """
    from iip.atlas.knowledge_adapter import AtlasKnowledgeAdapter

    evidence = AtlasKnowledgeAdapter.to_evidence(document)
    try:
        bridge.persist_evidence(evidence)
    except FileExistsError:
        # Append-only evidence store; an identical document (same
        # content hash) was already persisted -- not an error.
        pass


def collect_cvm_fii_history(
    ticker: str,
    cnpj: str,
    years: range,
    *,
    store: HistoricalSeriesStore,
    harvester: CvmFiiHTTPHarvester | None = None,
    bridge: Any = None,
) -> HistoricalSeries:
    """Collect and persist monthly CVM observations filtered by CNPJ.

    ``bridge`` (a ``KnowledgeBridge``) is optional: when given, each
    year's fetched CVM file is also persisted as real Atlas evidence
    (``04_Evidence/<document_id>.md``) via ``AtlasKnowledgeAdapter`` --
    previously this function built an ``AtlasDocument`` only to derive
    an id/hash for ``source_documents``, then discarded it without
    ever persisting it. When omitted, behavior is unchanged.
    """
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
        if bridge is not None:
            _persist_atlas_evidence(bridge, document)
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
                    rentabilidade_patrimonial_mes=values.get(
                        "Percentual_Rentabilidade_Patrimonial_Mes"
                    ),
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


def collect_cvm_diario_history(
    ticker: str,
    cnpj: str,
    year_months: tuple[tuple[int, int], ...],
    *,
    store: HistoricalSeriesStore,
    harvester: Any = None,
    bridge: Any = None,
) -> HistoricalSeries:
    """Collect and persist a NAV-per-quota history from CVM's Informe
    Diario (ICVM 555 general funds dataset), for asset classes not
    covered by the FII-specific dataset (etf, fixed_income).

    One observation per requested competencia month (its latest day),
    same cadence as ``collect_cvm_fii_history``. ``dividend_yield_mes``
    and ``rentabilidade_patrimonial_mes`` are not present in this
    dataset and are always None -- never approximated.

    ``bridge`` (a ``KnowledgeBridge``), when given, persists each
    fetched month's file as real Atlas evidence, same as
    ``collect_cvm_fii_history``.
    """
    from iip.sources.cvm_renda_fixa import build_diario_target

    normalized_cnpj = _digits(cnpj)
    if not normalized_cnpj:
        raise ValueError("cnpj must contain digits")

    if harvester is None:
        from iip.sources.cvm_renda_fixa_harvester import CvmRendaFixaHTTPHarvester

        harvester = CvmRendaFixaHTTPHarvester()

    observations: list[HistoricalObservation] = []
    source_documents: list[dict[str, Any]] = []

    for ano, mes in year_months:
        target = build_diario_target(ano, mes)
        result = harvester.fetch_diario(target)
        document = AtlasDocument.build(
            ticker=ticker,
            provider="cvm_renda_fixa",
            role="regulatory",
            url=target.url,
            final_url=target.url,
            content_type="application/zip",
            status_code=result.status_code,
            body=result.body,
            discovered_year=ano,
            title=f"CVM Informe Diario {ano:04d}-{mes:02d}",
        )
        if bridge is not None:
            _persist_atlas_evidence(bridge, document)
        matches = [
            item
            for item in result.informes
            if _digits(item.cnpj_fundo_classe) == normalized_cnpj
        ]
        source_documents.append(
            {
                "ano": ano,
                "mes": mes,
                "source_url": target.url,
                "document_id": document.document_id,
                "document_hash": document.content_hash,
                "matched": bool(matches),
            }
        )
        if not matches:
            continue
        latest = max(matches, key=lambda item: item.data_competencia)
        observations.append(
            HistoricalObservation(
                period=latest.data_competencia,
                patrimonio_liquido=latest.patrimonio_liquido,
                valor_patrimonial_cotas=latest.valor_cota,
                dividend_yield_mes=None,
                rentabilidade_patrimonial_mes=None,
                valor_ativo=latest.valor_total,
                total_numero_cotistas=(
                    float(latest.numero_cotistas)
                    if latest.numero_cotistas is not None
                    else None
                ),
                document_id=document.document_id,
                document_hash=document.content_hash,
                discovered_year=ano,
            )
        )

    observations.sort(key=lambda item: item.period)
    series = HistoricalSeries(
        ticker=ticker.upper(),
        cnpj=normalized_cnpj,
        provider="cvm_renda_fixa",
        observations=tuple(observations),
        source_documents=tuple(source_documents),
    )
    store.save(series)
    return series


def collect_cotahist_history(
    ticker: str,
    years: tuple[int, ...],
    *,
    store: HistoricalSeriesStore,
    harvester: Any = None,
    bridge: Any = None,
) -> HistoricalSeries:
    """Collect and persist a daily closing-price history from B3's own
    COTAHIST file -- for equities and ETFs, which CVM does not publish
    market price data for at all (see ``iip.sources.b3_cotahist``).

    Daily granularity (unlike the monthly cadence of the CVM-backed
    collectors), one HTTP fetch per requested year, tens of MB each --
    pass only the years actually needed. ``valor_patrimonial_cotas``
    holds the closing price (not a book/NAV value here); the fields
    with no COTAHIST equivalent (patrimonio_liquido, dividend_yield_mes,
    etc.) are left None, never approximated. ``cnpj`` is left empty --
    COTAHIST identifies instruments by ticker, not CNPJ.

    Not every listed ticker has COTAHIST coverage (confirmed live:
    LFTB11 has none, apparently thin/no secondary-market trading) --
    an empty result for a requested year is a real finding, not a bug.

    ``bridge`` (a ``KnowledgeBridge``), when given, persists each
    fetched year's whole annual file as real Atlas evidence, same as
    the CVM-backed collectors.
    """
    from iip.sources.b3_cotahist import build_target

    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError("ticker must not be empty")

    if harvester is None:
        from iip.sources.b3_cotahist_harvester import B3CotahistHTTPHarvester

        harvester = B3CotahistHTTPHarvester()

    observations: list[HistoricalObservation] = []
    source_documents: list[dict[str, Any]] = []

    for year in years:
        target = build_target(year)
        result = harvester.fetch(target, tickers=frozenset({normalized_ticker}))
        document = AtlasDocument.build(
            ticker=normalized_ticker,
            provider="b3_cotahist",
            role="market_data",
            url=target.url,
            final_url=result.final_url or target.url,
            content_type="application/zip",
            status_code=result.status_code,
            body=result.body,
            discovered_year=year,
            title=f"B3 COTAHIST {year}",
        )
        if bridge is not None:
            _persist_atlas_evidence(bridge, document)
        source_documents.append(
            {
                "year": year,
                "source_url": target.url,
                "document_id": document.document_id,
                "content_hash": document.content_hash,
                "matched": bool(result.quotes),
            }
        )
        for quote in result.quotes:
            observations.append(
                HistoricalObservation(
                    period=quote.date,
                    patrimonio_liquido=None,
                    valor_patrimonial_cotas=quote.close,
                    dividend_yield_mes=None,
                    rentabilidade_patrimonial_mes=None,
                    valor_ativo=None,
                    total_numero_cotistas=None,
                    document_id=document.document_id,
                    document_hash=document.content_hash,
                    discovered_year=year,
                )
            )

    observations.sort(key=lambda item: item.period)
    series = HistoricalSeries(
        ticker=normalized_ticker,
        cnpj="",
        provider="b3_cotahist",
        observations=tuple(observations),
        source_documents=tuple(source_documents),
    )
    store.save(series)
    return series


def collect_sparta_report_history(
    ticker: str,
    year_months: tuple[tuple[int, int], ...],
    *,
    store: HistoricalSeriesStore,
    harvester: Any = None,
    bridge: Any = None,
) -> HistoricalSeries:
    """Collect and persist a NAV-per-quota history from Sparta's own
    monthly management report PDFs (see ``iip.sources.sparta_reports``)
    -- for funds like CRAA11, whose CNPJ is confirmed absent from CVM's
    own FIAGRO open dataset.

    Genuinely more fragile than every CVM/B3-backed collector in this
    module: extraction depends on Sparta's PDF layout, not a
    structured CSV. A month whose report isn't published yet (404) or
    whose layout doesn't match is recorded in ``source_documents`` with
    ``matched: False`` and simply skipped -- never raises, never
    fabricates a value.

    ``cnpj`` is left empty on the returned series, same convention as
    ``collect_cotahist_history`` (this source identifies by ticker via
    the report URL, not CNPJ).
    """
    from urllib.error import HTTPError

    from iip.sources.sparta_reports import build_target

    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError("ticker must not be empty")

    if harvester is None:
        from iip.sources.sparta_reports_harvester import SpartaReportsHTTPHarvester

        harvester = SpartaReportsHTTPHarvester()

    observations: list[HistoricalObservation] = []
    source_documents: list[dict[str, Any]] = []

    for ano, mes in year_months:
        target = build_target(normalized_ticker, ano, mes)
        try:
            result = harvester.fetch(target)
        except HTTPError as exc:
            source_documents.append(
                {
                    "ano": ano,
                    "mes": mes,
                    "source_url": target.url,
                    "matched": False,
                    "error": f"HTTP {exc.code}",
                }
            )
            continue

        document = AtlasDocument.build(
            ticker=normalized_ticker,
            provider="sparta_reports",
            role="manager_report",
            url=target.url,
            final_url=result.final_url or target.url,
            content_type="application/pdf",
            status_code=result.status_code,
            body=result.body,
            discovered_year=ano,
            title=f"Sparta Relatorio Mensal {normalized_ticker} {ano:04d}-{mes:02d}",
        )
        if bridge is not None:
            _persist_atlas_evidence(bridge, document)

        matched = result.cota_patrimonial is not None
        source_documents.append(
            {
                "ano": ano,
                "mes": mes,
                "source_url": target.url,
                "document_id": document.document_id,
                "document_hash": document.content_hash,
                "matched": matched,
            }
        )
        if not matched:
            continue

        observations.append(
            HistoricalObservation(
                period=f"{ano:04d}-{mes:02d}-01",
                patrimonio_liquido=None,
                valor_patrimonial_cotas=result.cota_patrimonial,
                dividend_yield_mes=None,
                rentabilidade_patrimonial_mes=None,
                valor_ativo=None,
                total_numero_cotistas=None,
                document_id=document.document_id,
                document_hash=document.content_hash,
                discovered_year=ano,
            )
        )

    observations.sort(key=lambda item: item.period)
    series = HistoricalSeries(
        ticker=normalized_ticker,
        cnpj="",
        provider="sparta_reports",
        observations=tuple(observations),
        source_documents=tuple(source_documents),
    )
    store.save(series)
    return series
