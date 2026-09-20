"""Coleta dos indicadores macro do catálogo e gravação no ``MacroStore``.

Reaproveita os coletores que já existiam (``iip.sources.bacen`` e ``iip.sources.ibge``, com
seus transportes injetáveis); aqui só se traduz a competência de cada fonte para o formato do
contrato e se decide o que é provisório. Isolamento por indicador: a falha de um não derruba a
rodada, e o registro da coleta (``MacroStore.record_run``) guarda a tentativa que falhou.

Janela de cada coleta: diária, 400 dias; mensal, 40 meses; trimestral, 12 trimestres. Como o
armazenamento só grava o que mudou, repetir a coleta todo dia não duplica nada.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from iip.macro.contract import (
    BACEN_SGS,
    DAILY,
    IBGE_SIDRA,
    INDICATORS,
    QUARTERLY,
    TESOURO_DIRETO,
    MacroIndicator,
    indicator,
)
from iip.macro.store import IngestResult, MacroStore

DAILY_WINDOW_DAYS = 400
MONTHLY_WINDOW_MONTHS = 40
QUARTERLY_WINDOW = 12


@dataclass(frozen=True)
class CollectOutcome:
    indicator_id: str
    status: str  # "ok" ou "erro"
    detail: str
    result: IngestResult | None = None
    last_reference: str | None = None
    points: int = 0


def _bacen_reference(day: _dt.date, frequency: str) -> str:
    return day.isoformat() if frequency == DAILY else f"{day:%Y-%m}"


def _sidra_reference(period: str, frequency: str) -> str | None:
    """202608 -> 2026-08 (mensal); 202602 -> 2026-T2 (trimestral, MM = número do trimestre)."""
    if len(period) != 6 or not period.isdigit():
        return None
    year, part = period[:4], int(period[4:])
    if frequency == QUARTERLY:
        return f"{year}-T{part}" if 1 <= part <= 4 else None
    return f"{year}-{part:02d}" if 1 <= part <= 12 else None


def _months_ago(day: _dt.date, months: int) -> _dt.date:
    total = day.year * 12 + (day.month - 1) - months
    return _dt.date(total // 12, total % 12 + 1, 1)


Points = tuple[tuple[str, float | None, bool], ...]


def fetch_points(
    ind: MacroIndicator,
    *,
    today: _dt.date,
    bacen: Any,
    ibge: Any,
    tesouro: Any = None,
) -> tuple[Points, dict[str, str]]:
    """Os pontos da fonte como (competência, valor, provisório) e as notas de proveniência por
    competência (o vencimento da NTN-B). Levanta se a fonte falha."""
    if ind.source == TESOURO_DIRETO:
        series = tesouro.fetch_long_ntnb_series()
        return (
            tuple(
                (r.reference_date.isoformat(), round(r.real_yield * 100, 4), False)
                for r in series
            ),
            {
                r.reference_date.isoformat(): f"{r.title}, vencimento {r.maturity:%d/%m/%Y}"
                for r in series
            },
        )
    if ind.source == BACEN_SGS:
        from iip.sources.bacen import build_target

        if ind.frequency == DAILY:
            start = today - _dt.timedelta(days=DAILY_WINDOW_DAYS)
        else:
            start = _months_ago(today, MONTHLY_WINDOW_MONTHS)
        fetched = bacen.fetch(build_target(int(ind.source_ref), start, today))
        return (
            tuple(
                (
                    _bacen_reference(p.date, ind.frequency),
                    p.value,
                    ind.accumulates_in_month
                    and (p.date.year, p.date.month) == (today.year, today.month),
                )
                for p in fetched.points
            ),
            {},
        )
    if ind.source == IBGE_SIDRA:
        from iip.sources.ibge import build_target as build_ibge

        agregado, variavel = (int(part) for part in ind.source_ref.split("/"))
        periods = (
            f"-{QUARTERLY_WINDOW}"
            if ind.frequency == QUARTERLY
            else f"-{MONTHLY_WINDOW_MONTHS}"
        )
        fetched = ibge.fetch(
            build_ibge(agregado, variavel, periodos=periods, localidades="N1[all]")
        )
        points = []
        for p in fetched.points:
            reference = _sidra_reference(p.periodo, ind.frequency)
            # o IBGE marca "sem dado" com texto; o leitor devolve None: não vira zero
            if reference is not None and p.value is not None:
                points.append((reference, p.value, False))
        return tuple(points), {}
    raise ValueError(f"fonte desconhecida para {ind.id}: {ind.source}")


def collect_indicator(
    ind: MacroIndicator,
    store: MacroStore,
    *,
    today: _dt.date,
    bacen: Any,
    ibge: Any,
    tesouro: Any = None,
) -> CollectOutcome:
    stamp = today.isoformat()
    try:
        points, notes = fetch_points(
            ind, today=today, bacen=bacen, ibge=ibge, tesouro=tesouro
        )
        if not points:
            raise ValueError("a fonte não devolveu nenhum ponto")
        result = store.ingest(ind.id, points, collected_at=stamp, notes=notes)
    # isolamento por indicador, como nos lotes da carteira
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        store.record_run(ind.id, collected_at=stamp, status="erro", detail=detail)
        return CollectOutcome(ind.id, "erro", detail)
    store.record_run(ind.id, collected_at=stamp, status="ok", result=result)
    return CollectOutcome(
        ind.id,
        "ok",
        f"{result.new} novos, {result.revised} revisados",
        result,
        last_reference=max(p[0] for p in points),
        points=len(points),
    )


def collect_macro(
    indicator_ids: tuple[str, ...] | None,
    store: MacroStore,
    *,
    today: _dt.date,
    bacen: Any = None,
    ibge: Any = None,
    tesouro: Any = None,
    on_outcome: Callable[[CollectOutcome], None] | None = None,
) -> tuple[CollectOutcome, ...]:
    """Coleta os indicadores pedidos (todos do catálogo, sem lista). Um id fora do catálogo
    levanta ``KeyError`` antes de qualquer coleta."""
    chosen = (
        tuple(indicator(i) for i in indicator_ids)
        if indicator_ids
        else tuple(INDICATORS.values())
    )
    if bacen is None:
        from iip.sources.bacen_harvester import BacenHTTPHarvester

        bacen = BacenHTTPHarvester()
    if ibge is None:
        from iip.sources.ibge_harvester import IbgeHTTPHarvester

        ibge = IbgeHTTPHarvester()
    if tesouro is None:
        from iip.sources.tesouro_direto_harvester import TesouroDiretoHTTPHarvester

        tesouro = TesouroDiretoHTTPHarvester()
    outcomes = []
    for ind in chosen:
        outcome = collect_indicator(
            ind, store, today=today, bacen=bacen, ibge=ibge, tesouro=tesouro
        )
        outcomes.append(outcome)
        if on_outcome:
            on_outcome(outcome)
    return tuple(outcomes)
