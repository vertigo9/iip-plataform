"""Exposição e concentração da carteira, a partir do snapshot real das posições.

A fonte é ``02_Portfolio/Current.md`` (Investidor10, lido por
``iip.portfolio.vault_snapshot.parse_current_snapshot``): quantidade, valor e peso de cada
posição ativa, incluindo a renda fixa bancária que o registro de ativos não acompanha. Cada
posição é classificada pelo registro (``PortfolioAsset``); o que o registro não classifica
aparece como ``SEM_CLASSIFICACAO`` e é dito, nunca escondido nem adivinhado.

O peso usado é valor da posição / valor total das posições (a regra 2 da nota diz que o valor
individual prevalece sobre os totais). Quatro visões: classe, gestora, setor/segmento e perfil
de risco. Ações não têm gestora, então "gestora" só descreve os fundos; e o campo
setor/segmento mistura, de propósito e declarado, o setor das ações com o segmento dos fundos.

Só descreve: os limites de alerta são de ATENÇÃO, configuráveis, e não uma política de
alocação (o peso-alvo da carteira segue vazio por decisão do usuário).
"""

from __future__ import annotations

import datetime as _dt
from collections import defaultdict
from dataclasses import dataclass

from iip.portfolio.registry import (
    ALL_PORTFOLIO_ASSETS,
    PORTFOLIO_ASSETS,
    PortfolioAsset,
)
from iip.portfolio.vault_snapshot import _ID_TO_REGISTRY_TICKER
from iip.universal.portfolio_state import PortfolioState, PositionState

SEM_CLASSIFICACAO = "(sem classificação)"

DEFAULT_GROUP_LIMIT = 0.20
DEFAULT_POSITION_LIMIT = 0.10
# um snapshot mais velho que isto (dias) tem pesos que já andaram com os preços
STALE_AFTER_DAYS = 7
# cobertura abaixo disto numa visão: o resultado descreve pouco da carteira
LOW_COVERAGE = 0.5

DIMENSIONS = ("Classe", "Gestora", "Setor / segmento", "Perfil de risco")
# Onde um grupo pesado é concentração de risco. A divisão por classe e por perfil é
# alocação: sem peso-alvo não há o que dizer de "muito" ou "pouco", então só se mostra.
ALERT_DIMENSIONS = ("Gestora", "Setor / segmento")


@dataclass(frozen=True)
class ExposureRow:
    label: str
    weight: float
    value: float
    count: int
    tickers: tuple[str, ...]


@dataclass(frozen=True)
class DimensionExposure:
    name: str
    rows: tuple[
        ExposureRow, ...
    ]  # maior peso primeiro; a linha sem classificação por último
    classified_weight: float

    @property
    def low_coverage(self) -> bool:
        return self.classified_weight < LOW_COVERAGE


@dataclass(frozen=True)
class ConcentrationFlag:
    kind: str  # "grupo" ou "posição"
    dimension: str
    label: str
    weight: float
    limit: float


@dataclass(frozen=True)
class ExposureReport:
    as_of: _dt.date | None
    age_days: int | None
    total_value: float
    position_count: int
    dimensions: tuple[DimensionExposure, ...]
    flags: tuple[ConcentrationFlag, ...]
    # tickers do registro de ativos que não estão no snapshot (a carteira estaria incompleta)
    missing_from_snapshot: tuple[str, ...]
    group_limit: float
    position_limit: float
    # posições de ativos ENCERRADOS no registro que voltaram ao snapshot (ticker, encerrado em):
    # o job não as atualiza até o ativo ser reativado no registro
    closed_in_snapshot: tuple[tuple[str, str], ...] = ()

    @property
    def stale(self) -> bool:
        return self.age_days is not None and self.age_days > STALE_AFTER_DAYS


def _registry_asset(position: PositionState) -> PortfolioAsset | None:
    ticker = _ID_TO_REGISTRY_TICKER.get(position.ticker, position.ticker)
    # inclui as encerradas: uma posição que voltou ao snapshot mantém a classificação
    return next((a for a in ALL_PORTFOLIO_ASSETS if a.ticker == ticker), None)


def _class_label(position: PositionState, asset: PortfolioAsset | None) -> str:
    if asset is None:
        return (
            "Renda fixa bancária"
            if position.asset_class == "fixed_income"
            else SEM_CLASSIFICACAO
        )
    if asset.asset_class == "equity":
        return "Ações"
    if asset.asset_class == "fund":
        return asset.subtype or "Fundo"
    if asset.asset_class == "etf":
        return "ETF"
    if "FMP" in (asset.subtype or "").upper():
        return "FMP-FGTS"
    return asset.asset_class


def _labels(position: PositionState) -> tuple[str, str, str, str]:
    asset = _registry_asset(position)
    sector_or_segment = (asset.segment or asset.sector) if asset else None
    return (
        _class_label(position, asset),
        (asset.manager if asset else None) or SEM_CLASSIFICACAO,
        sector_or_segment or SEM_CLASSIFICACAO,
        (asset.risk_profile if asset else None) or SEM_CLASSIFICACAO,
    )


def _dimension(
    name: str, index: int, positions: tuple[PositionState, ...], total: float
) -> DimensionExposure:
    groups: dict[str, list[PositionState]] = defaultdict(list)
    for position in positions:
        groups[_labels(position)[index]].append(position)
    rows = [
        ExposureRow(
            label,
            sum(p.market_value for p in members) / total,
            sum(p.market_value for p in members),
            len(members),
            tuple(sorted(p.ticker for p in members)),
        )
        for label, members in groups.items()
    ]
    rows.sort(key=lambda r: (r.label == SEM_CLASSIFICACAO, -r.weight, r.label))
    classified = sum(r.weight for r in rows if r.label != SEM_CLASSIFICACAO)
    return DimensionExposure(name, tuple(rows), classified)


def build_exposure(
    state: PortfolioState,
    *,
    today: _dt.date,
    group_limit: float = DEFAULT_GROUP_LIMIT,
    position_limit: float = DEFAULT_POSITION_LIMIT,
) -> ExposureReport:
    positions = tuple(p for p in state.positions if p.market_value > 0)
    total = sum(p.market_value for p in positions)
    if total <= 0:
        raise ValueError("o snapshot não tem posição com valor: nada a analisar")

    dimensions = tuple(
        _dimension(name, index, positions, total)
        for index, name in enumerate(DIMENSIONS)
    )
    flags = [
        ConcentrationFlag(
            "posição", "Posição", p.ticker, p.market_value / total, position_limit
        )
        for p in positions
        if p.market_value / total > position_limit
    ]
    for dimension in dimensions:
        flags.extend(
            ConcentrationFlag(
                "grupo", dimension.name, row.label, row.weight, group_limit
            )
            for row in dimension.rows
            if row.label != SEM_CLASSIFICACAO
            and row.weight > group_limit
            and dimension.name in ALERT_DIMENSIONS
        )
    flags.sort(key=lambda f: (-f.weight, f.dimension, f.label))

    try:
        as_of = _dt.date.fromisoformat(state.as_of)
    except ValueError:
        as_of = None
    in_snapshot = {
        _ID_TO_REGISTRY_TICKER.get(p.ticker, p.ticker) for p in state.positions
    }
    return ExposureReport(
        as_of=as_of,
        age_days=(today - as_of).days if as_of else None,
        total_value=total,
        position_count=len(positions),
        dimensions=dimensions,
        flags=tuple(flags),
        missing_from_snapshot=tuple(
            sorted(a.ticker for a in PORTFOLIO_ASSETS if a.ticker not in in_snapshot)
        ),
        group_limit=group_limit,
        position_limit=position_limit,
        closed_in_snapshot=tuple(
            sorted(
                (a.ticker, a.closed_on)
                for a in ALL_PORTFOLIO_ASSETS
                if a.closed_on and a.ticker in in_snapshot
            )
        ),
    )
