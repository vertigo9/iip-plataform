"""O contexto macroeconômico: o último valor de cada indicador, a comparação com 12 meses
antes, o frescor e a conferência entre fontes.

Só descreve o que está guardado no ``MacroStore``; não coleta nada e não interpreta (não diz
que a Selic "é alta" nem o que fazer com a carteira). Cenários e a ligação com as premissas de
valuation são o passo seguinte da Entrega B.
"""

from __future__ import annotations

import calendar
import datetime as _dt
from dataclasses import dataclass

from iip.macro.contract import (
    DAILY,
    INDICATORS,
    QUARTERLY,
    MacroIndicator,
    MacroObservation,
)
from iip.macro.store import MacroStore

# duas fontes do mesmo indicador concordam se a diferença fica abaixo disto (na unidade)
CROSS_CHECK_TOLERANCE = 0.051
CROSS_CHECK_WINDOW = 6


@dataclass(frozen=True)
class MacroReading:
    indicator: MacroIndicator
    latest: MacroObservation | None
    year_ago: MacroObservation | None
    change: float | None  # em pp ou em %, conforme ``change_kind``
    recent: tuple[MacroObservation, ...]  # as últimas competências, da mais antiga
    stale: bool
    last_ok: str | None  # a última coleta bem-sucedida
    first_collected_at: str | None
    revisions: int  # competências com mais de um valor guardado

    @property
    def missing(self) -> bool:
        return self.latest is None


@dataclass(frozen=True)
class SourceCheck:
    a: str
    b: str
    compared: int
    max_difference: float | None
    agrees: bool


@dataclass(frozen=True)
class MacroContext:
    today: _dt.date
    readings: tuple[MacroReading, ...]
    source_checks: tuple[SourceCheck, ...]

    @property
    def stale(self) -> tuple[MacroReading, ...]:
        return tuple(r for r in self.readings if r.stale)

    @property
    def missing(self) -> tuple[MacroReading, ...]:
        return tuple(r for r in self.readings if r.missing)

    @property
    def first_collected_at(self) -> str | None:
        stamps = [r.first_collected_at for r in self.readings if r.first_collected_at]
        return min(stamps) if stamps else None


def period_end(reference: str, frequency: str) -> _dt.date:
    """O último dia da competência (a data a partir da qual o dado poderia existir)."""
    if frequency == DAILY:
        return _dt.date.fromisoformat(reference)
    if frequency == QUARTERLY:
        year, quarter = int(reference[:4]), int(reference[-1])
        month = quarter * 3
    else:
        year, month = int(reference[:4]), int(reference[5:7])
    return _dt.date(year, month, calendar.monthrange(year, month)[1])


def _shift(reference: str, frequency: str) -> str:
    """A competência de um ano antes (12 mensais, 4 trimestrais ou 365 dias)."""
    if frequency == DAILY:
        return (_dt.date.fromisoformat(reference) - _dt.timedelta(days=365)).isoformat()
    if frequency == QUARTERLY:
        year, quarter = int(reference[:4]), int(reference[-1])
        total = year * 4 + (quarter - 1) - 4
        return f"{total // 4}-T{total % 4 + 1}"
    year, month = int(reference[:4]), int(reference[5:7])
    total = year * 12 + (month - 1) - 12
    return f"{total // 12}-{total % 12 + 1:02d}"


def _year_ago(
    observations: tuple[MacroObservation, ...], latest: MacroObservation, frequency: str
) -> MacroObservation | None:
    target = _shift(latest.reference, frequency)
    if frequency == DAILY:  # o dia pode não ter dado (fim de semana): o último até ele
        earlier = [o for o in observations if o.reference <= target]
        return earlier[-1] if earlier else None
    return next((o for o in observations if o.reference == target), None)


def _change(
    ind: MacroIndicator, latest: MacroObservation, before: MacroObservation | None
) -> float | None:
    if before is None or latest.value is None or before.value is None:
        return None
    if ind.change_kind == "pp":
        return latest.value - before.value
    if ind.change_kind == "pct" and before.value:
        return (latest.value / before.value - 1) * 100
    return None


def read_indicator(
    ind: MacroIndicator, store: MacroStore, today: _dt.date
) -> MacroReading:
    observations = tuple(o for o in store.latest(ind.id) if o.value is not None)
    run = store.runs().get(ind.id, {})
    common = {
        "indicator": ind,
        "last_ok": run.get("last_ok"),
        "first_collected_at": store.first_collected_at(ind.id),
        "revisions": len(store.revisions(ind.id)),
    }
    if not observations:
        return MacroReading(
            **common, latest=None, year_ago=None, change=None, recent=(), stale=False
        )
    latest = observations[-1]
    before = _year_ago(observations, latest, ind.frequency)
    age_days = (today - period_end(latest.reference, ind.frequency)).days
    return MacroReading(
        **common,
        latest=latest,
        year_ago=before,
        change=_change(ind, latest, before),
        recent=observations[-3:],
        stale=age_days > ind.stale_after_days,
    )


def _source_check(
    a: MacroIndicator, b: MacroIndicator, store: MacroStore
) -> SourceCheck:
    """Compara as duas fontes nas competências em comum. Se a frequência difere (o trimestre
    do IBGE contra o mês do BACEN), compara o trimestre com o mês em que ele fecha."""
    left = {o.reference: o.value for o in store.latest(a.id) if o.value is not None}
    right = {o.reference: o.value for o in store.latest(b.id) if o.value is not None}
    pairs: list[tuple[float, float]] = []
    if a.frequency == b.frequency:
        common = sorted(set(left) & set(right))[-CROSS_CHECK_WINDOW:]
        pairs = [(left[r], right[r]) for r in common]
    else:
        monthly, quarterly = (
            (left, right) if a.frequency != QUARTERLY else (right, left)
        )
        for reference in sorted(quarterly)[-CROSS_CHECK_WINDOW:]:
            closing = f"{reference[:4]}-{int(reference[-1]) * 3:02d}"
            if closing in monthly:
                pairs.append((monthly[closing], quarterly[reference]))
    if not pairs:
        return SourceCheck(a.id, b.id, 0, None, False)
    worst = max(abs(x - y) for x, y in pairs)
    return SourceCheck(a.id, b.id, len(pairs), worst, worst <= CROSS_CHECK_TOLERANCE)


def build_context(store: MacroStore, today: _dt.date) -> MacroContext:
    readings = tuple(read_indicator(ind, store, today) for ind in INDICATORS.values())
    seen: set[frozenset[str]] = set()
    checks = []
    for ind in INDICATORS.values():
        if not ind.cross_check_with:
            continue
        pair = frozenset({ind.id, ind.cross_check_with})
        if pair in seen:
            continue
        seen.add(pair)
        checks.append(_source_check(ind, INDICATORS[ind.cross_check_with], store))
    # a desocupação: o mensal do BACEN contra o trimestral do IBGE
    checks.append(
        _source_check(
            INDICATORS["desocupacao_mensal"], INDICATORS["desocupacao_ibge"], store
        )
    )
    return MacroContext(today, readings, tuple(checks))
