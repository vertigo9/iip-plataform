"""As camadas do patrimônio: o mesmo snapshot visto por classe, ativo, setor, segmento e tipo.

Só LEITURA: descreve o peso ATUAL das posições em camadas diferentes, cada percentual com o seu
denominador dito pelo nome. Não define alvos nem limites (nem por ativo nem por camada), não
altera a política de pesos-alvo, não sinaliza nada e não decide, aporta nem rebalanceia (o módulo
não importa essas camadas; há teste de importação).

Os denominadores, sempre explícitos:
  - ``weight_total_pct``  (peso_total_pct): valor / patrimônio total (a base A: a soma das
    posições do snapshot, renda fixa bancária incluída);
  - ``weight_class_pct``  (peso_classe_pct): valor / valor da classe (Ações ou FIIs);
  - ``weight_group_pct``  (peso_setor_pct, peso_segmento_pct, peso_tipo_pct): valor do ativo /
    valor do grupo (o setor, o segmento ou o tipo em que ele está).
BBSE3 = 12,57% do patrimônio e ≈ 28,4% das ações são duas leituras do MESMO ativo.

Camadas: 1 classe; 2 ativo; 3 ações consolidado (dentro da classe); 4 ações por setor; 5 ações
por segmento; 6 FIIs, consolidado, por tipo e por segmento. FI-Infra e FIAgro são classes
próprias (só na camada 1 e 2), fora da camada de FIIs. ETF, FMP-FGTS e CDBs só têm as camadas 1 e
2. Os CDBs entram agrupados numa linha de renda fixa bancária, como na política.

Alvos derivados: o alvo de cada ativo é definido UMA vez, na base A (política de pesos-alvo);
as agregações são calculadas dele e só valem quando TODOS os ativos do grupo têm alvo
``definido``. Até lá o grupo aparece como ``parcial`` (o que já está definido) ou ``pendente``,
nunca como um total inventado.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from iip.portfolio.registry import get_asset
from iip.portfolio.target_policy import (
    BANK_FIXED_INCOME_ID,
    LEGACY_ALIASES,
    SnapshotRow,
    TargetPolicy,
)

CLASS_LABELS = {
    "acao": "Ações",
    "fii": "FIIs",
    "fi-infra": "FI-Infra",
    "fiagro": "FIAgro",
    "renda_fixa": "Renda fixa bancária",
    "etf": "ETFs",
    "fundo": "Fundos (FMP-FGTS)",
}
STOCKS, FIIS = "acao", "fii"
UNCLASSIFIED = "sem classificação"


@dataclass(frozen=True)
class Holding:
    id: str
    name: str
    asset_class: str
    value: float
    weight_total_pct: float
    sector: str = ""  # só ações
    segment: str = ""  # ações: o segmento; FIIs: o segmento do fundo
    structure: str = ""  # só FIIs: o tipo (Tijolo, Papel...)
    members: tuple[str, ...] = ()  # os ids do snapshot que a linha agrupa (CDBs)
    target_pct: float | None = (
        None  # o alvo por ativo (base A), só se ``definido`` na política
    )


@dataclass(frozen=True)
class TargetAggregate:
    """A soma dos alvos definidos de um grupo, e o quanto do grupo já está definido."""

    members: int
    defined: int
    sum_pct: float | None  # a soma dos alvos definidos (None se nenhum)

    @property
    def state(self) -> str:
        if self.members and self.defined == self.members:
            return "completo"
        return "parcial" if self.defined else "pendente"


@dataclass(frozen=True)
class GroupView:
    label: str
    value: float
    weight_total_pct: float
    weight_class_pct: (
        float | None
    )  # dentro da classe; None quando o grupo é a própria classe
    holdings: tuple[Holding, ...]
    target: TargetAggregate
    parent: str = ""  # o setor de um segmento

    def weight_group_pct(self, holding: Holding) -> float:
        return holding.value / self.value * 100 if self.value else 0.0


@dataclass(frozen=True)
class Layers:
    total: float
    position_count: int
    classes: tuple[GroupView, ...]  # camada 1
    assets: tuple[Holding, ...]  # camada 2
    stocks: GroupView | None  # camada 3 (a classe Ações)
    stock_sectors: tuple[GroupView, ...]  # camada 4
    stock_segments: tuple[GroupView, ...]  # camada 5
    fiis: GroupView | None  # camada 6, consolidado
    fii_types: tuple[GroupView, ...]  # camada 6, por tipo
    fii_segments: tuple[GroupView, ...]  # camada 6, por segmento
    class_targets: dict[str, TargetAggregate] = field(default_factory=dict)
    unclassified: tuple[str, ...] = ()  # ativos sem setor/segmento/tipo no registro

    def derived_class_share(self, holding: Holding) -> float | None:
        """O alvo do ativo dentro da classe: só quando a classe INTEIRA tem alvo definido."""
        aggregate = self.class_targets.get(holding.asset_class)
        if (
            holding.target_pct is None
            or aggregate is None
            or aggregate.state != "completo"
        ):
            return None
        return (
            holding.target_pct / aggregate.sum_pct * 100 if aggregate.sum_pct else None
        )


def _registry_asset(row_id: str):
    ticker = next(iter(LEGACY_ALIASES.get(row_id, ())), row_id)
    return get_asset(ticker, include_closed=True)


def _target_of(policy: TargetPolicy | None, holding_id: str) -> float | None:
    if policy is None:
        return None
    line = policy.resolve(holding_id)
    if line is None or line.status != "definido":
        return None
    return line.target_pct


def _holdings(
    rows: tuple[SnapshotRow, ...], policy: TargetPolicy | None
) -> list[Holding]:
    total = sum(r.value for r in rows)
    holdings: list[Holding] = []
    bank = [r for r in rows if r.asset_class == "renda_fixa"]
    for row in rows:
        if row.asset_class == "renda_fixa":
            continue
        asset = _registry_asset(row.id)
        sector = segment = structure = ""
        if row.asset_class == STOCKS:
            sector = (asset.sector if asset else None) or UNCLASSIFIED
            segment = (asset.industry if asset else None) or UNCLASSIFIED
        elif row.asset_class == FIIS:
            structure = (asset.structure if asset else None) or UNCLASSIFIED
            segment = (asset.segment if asset else None) or UNCLASSIFIED
        holdings.append(
            Holding(
                row.id,
                row.name,
                row.asset_class,
                row.value,
                row.value / total * 100,
                sector,
                segment,
                structure,
                target_pct=_target_of(policy, row.id),
            )
        )
    if bank:
        value = sum(r.value for r in bank)
        holdings.append(
            Holding(
                BANK_FIXED_INCOME_ID,
                "Renda fixa bancária (CDBs)",
                "renda_fixa",
                value,
                value / total * 100,
                members=tuple(r.id for r in bank),
                target_pct=_target_of(policy, BANK_FIXED_INCOME_ID),
            )
        )
    return holdings


def _aggregate(holdings: list[Holding]) -> TargetAggregate:
    defined = [h.target_pct for h in holdings if h.target_pct is not None]
    return TargetAggregate(
        len(holdings), len(defined), sum(defined) if defined else None
    )


def _group(
    label: str,
    holdings: list[Holding],
    total: float,
    class_value: float | None,
    parent: str = "",
) -> GroupView:
    value = sum(h.value for h in holdings)
    ordered = tuple(sorted(holdings, key=lambda h: -h.value))
    return GroupView(
        label,
        value,
        value / total * 100,
        value / class_value * 100 if class_value else None,
        ordered,
        _aggregate(holdings),
        parent,
    )


def _by(
    holdings: list[Holding], key, total: float, class_value: float, parent=None
) -> tuple[GroupView, ...]:
    buckets: dict[str, list[Holding]] = defaultdict(list)
    for holding in holdings:
        buckets[key(holding)].append(holding)
    groups = [
        _group(
            label,
            members,
            total,
            class_value,
            parent(members[0]) if parent else "",
        )
        for label, members in buckets.items()
    ]
    return tuple(sorted(groups, key=lambda g: -g.value))


def build_layers(
    rows: tuple[SnapshotRow, ...], policy: TargetPolicy | None = None
) -> Layers:
    """As seis camadas do snapshot; com ``policy``, mostra também o que já está definido nela
    (alvos derivados, só leitura). Nada é gravado nem alterado."""
    total = sum(r.value for r in rows)
    if total <= 0:
        raise ValueError("o snapshot não tem valor: nada a mostrar")
    holdings = _holdings(rows, policy)

    by_class: dict[str, list[Holding]] = defaultdict(list)
    for holding in holdings:
        by_class[holding.asset_class].append(holding)
    classes = tuple(
        sorted(
            (
                _group(CLASS_LABELS.get(k, k), members, total, None)
                for k, members in by_class.items()
            ),
            key=lambda g: -g.value,
        )
    )
    class_targets = {k: _aggregate(members) for k, members in by_class.items()}

    stock_holdings = by_class.get(STOCKS, [])
    stocks = (
        _group(CLASS_LABELS[STOCKS], stock_holdings, total, None)
        if stock_holdings
        else None
    )
    stock_value = stocks.value if stocks else 0.0
    fii_holdings = by_class.get(FIIS, [])
    fiis = (
        _group(CLASS_LABELS[FIIS], fii_holdings, total, None) if fii_holdings else None
    )
    fii_value = fiis.value if fiis else 0.0

    unclassified = tuple(
        h.id for h in holdings if UNCLASSIFIED in (h.sector, h.segment, h.structure)
    )
    return Layers(
        total=total,
        position_count=len(rows),
        classes=classes,
        assets=tuple(sorted(holdings, key=lambda h: -h.value)),
        stocks=stocks,
        stock_sectors=_by(stock_holdings, lambda h: h.sector, total, stock_value),
        stock_segments=_by(
            stock_holdings,
            lambda h: h.segment,
            total,
            stock_value,
            parent=lambda h: h.sector,
        ),
        fiis=fiis,
        fii_types=_by(fii_holdings, lambda h: h.structure, total, fii_value),
        fii_segments=_by(fii_holdings, lambda h: h.segment, total, fii_value),
        class_targets=class_targets,
        unclassified=unclassified,
    )
