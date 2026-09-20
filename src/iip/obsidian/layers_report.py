"""As camadas do patrimônio como nota do vault: ``02_Portfolio/Camadas.md``.

Sobrescrita a cada execução. SOMENTE LEITURA: mostra o peso atual em camadas (classe, ativo,
ações consolidado, setor, segmento e FIIs por tipo e segmento), cada percentual com o nome do
seu denominador, e o que a política de pesos-alvo já tem definido (alvo por ativo na base A e
o que dele se deriva). Não define alvo nem limite, não sinaliza nada e não decide, aporta nem
rebalanceia.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from iip.obsidian.frontmatter import flow_line
from iip.portfolio.layers import (
    CLASS_LABELS,
    GroupView,
    Holding,
    Layers,
    TargetAggregate,
)

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Camadas.md"


def _brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}".replace(".", ",") + "%"


def _target(holding: Holding) -> str:
    return _pct(holding.target_pct) if holding.target_pct is not None else "pendente"


def _aggregate(aggregate: TargetAggregate) -> str:
    """O alvo derivado de um grupo: só é total quando TODOS os ativos dele têm alvo."""
    if aggregate.state == "completo":
        return f"{_pct(aggregate.sum_pct)} ({aggregate.defined} de {aggregate.members})"
    if aggregate.state == "parcial":
        return (
            f"parcial: {_pct(aggregate.sum_pct)} "
            f"({aggregate.defined} de {aggregate.members} definidos)"
        )
    return f"pendente (0 de {aggregate.members} definidos)"


def _derived_in_class(layers: Layers, holding: Holding) -> str:
    share = layers.derived_class_share(holding)
    return _pct(share) if share is not None else "pendente"


def _label(holding: Holding) -> str:
    return f"`{holding.id}`" + (
        "" if holding.name == holding.id else f" · {holding.name}"
    )


def _frontmatter(
    layers: Layers,
    today: _dt.date,
    snapshot_date: _dt.date | None,
    policy_hash: str | None,
) -> list[str]:
    age = (today - snapshot_date).days if snapshot_date else None
    classes = [
        {
            "classe": g.label,
            "valor": round(g.value, 2),
            "peso_total_pct": round(g.weight_total_pct, 2),
        }
        for g in layers.classes
    ]
    defined = sum(1 for h in layers.assets if h.target_pct is not None)
    return [
        "---",
        "type: portfolio_layers",
        f"date: {today.isoformat()}",
        flow_line(
            "snapshot_data", snapshot_date.isoformat() if snapshot_date else None
        ),
        flow_line("snapshot_dias", age),
        flow_line("patrimonio_total", round(layers.total, 2)),
        flow_line("posicoes", layers.position_count),
        flow_line("linhas_de_ativo", len(layers.assets)),
        flow_line("classes", classes),
        flow_line("ativos_sem_classificacao", list(layers.unclassified)),
        flow_line("ativos_com_alvo_definido", defined),
        flow_line("politica_hash", policy_hash),
        "---",
    ]


def _group_table(
    groups: tuple[GroupView, ...], first: str, *, parent: bool = False
) -> list[str]:
    head = f"| {first} | " + ("Setor | " if parent else "")
    lines = [
        head
        + "Ativos | Valor | peso_total_pct | peso_classe_pct | Alvo derivado (base A) |",
        "|---|" + ("---|" if parent else "") + "---:|---:|---:|---:|---|",
    ]
    for g in groups:
        lines.append(
            f"| {g.label} | "
            + (f"{g.parent} | " if parent else "")
            + f"{len(g.holdings)} | {_brl(g.value)} | {_pct(g.weight_total_pct)} | "
            f"{_pct(g.weight_class_pct)} | {_aggregate(g.target)} |"
        )
    return lines


def _detail_table(
    groups: tuple[GroupView, ...], first: str, group_column: str
) -> list[str]:
    lines = [
        f"| {first} | Ativo | peso_total_pct | peso_classe_pct | {group_column} | "
        "Alvo (base A) |",
        "|---|---|---:|---:|---:|---|",
    ]
    for g in groups:
        for h in g.holdings:
            class_pct = g.weight_class_pct * h.value / g.value if g.value else None
            lines.append(
                f"| {g.label} | `{h.id}` | {_pct(h.weight_total_pct)} | {_pct(class_pct)} | "
                f"{_pct(g.weight_group_pct(h))} | {_target(h)} |"
            )
    return lines


def render_layers_report(
    layers: Layers,
    *,
    today: _dt.date,
    snapshot_date: _dt.date | None = None,
    policy_hash: str | None = None,
    policy_status: str | None = None,
) -> str:
    class_value = {g.label: g.value for g in layers.classes}
    age = (today - snapshot_date).days if snapshot_date else None
    lines = [
        *_frontmatter(layers, today, snapshot_date, policy_hash),
        "",
        "# Camadas do patrimônio",
        "",
        f"O mesmo snapshot ({layers.position_count} posições, {_brl(layers.total)}"
        + (f"; de {snapshot_date:%d/%m/%Y}, {age} dias" if snapshot_date else "")
        + ") em seis camadas. É só LEITURA do peso ATUAL: não define alvo nem limite, não "
        "sinaliza nada e não decide, aporta nem rebalanceia. Os alvos, quando existirem, vêm "
        "da política de pesos-alvo"
        + (f" (hoje {policy_status})" if policy_status else " (ainda não criada)")
        + ".",
        "",
        "## Como ler os percentuais",
        "",
        "Cada coluna diz o seu denominador. O mesmo ativo aparece com números diferentes em "
        "camadas diferentes, e todos estão certos:",
        "",
        "| Coluna | Denominador |",
        "|---|---|",
        f"| `peso_total_pct` | o patrimônio total, a base A: a soma das posições do snapshot "
        f"({_brl(layers.total)}), renda fixa bancária incluída |",
        "| `peso_classe_pct` | o valor da classe do ativo (as ações, ou os FIIs) |",
        "| `peso_setor_pct`, `peso_segmento_pct`, `peso_tipo_pct` | o valor do grupo em que o "
        "ativo está (o setor, o segmento ou o tipo) |",
        "| Alvo (base A) | o alvo do ativo na política, como % do patrimônio total; "
        "`pendente` enquanto não estiver `definido` |",
        "",
        "## 1. Patrimônio por classe",
        "",
        "| Classe | Ativos | Valor | peso_total_pct | Alvo derivado (base A) |",
        "|---|---:|---:|---:|---|",
    ]
    for g in layers.classes:
        lines.append(
            f"| {g.label} | {len(g.holdings)} | {_brl(g.value)} | {_pct(g.weight_total_pct)} | "
            f"{_aggregate(g.target)} |"
        )

    lines += [
        "",
        "## 2. Patrimônio por ativo",
        "",
        "Os CDBs entram agrupados numa linha de renda fixa bancária, como na política.",
        "",
        "| Ativo | Classe | Valor | peso_total_pct | peso_classe_pct | Alvo (base A) | "
        "Alvo na classe (derivado) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for h in layers.assets:
        label = CLASS_LABELS.get(h.asset_class, h.asset_class)
        in_class = (
            h.value / class_value[label] * 100 if class_value.get(label) else None
        )
        lines.append(
            f"| {_label(h)} | {label} | {_brl(h.value)} | {_pct(h.weight_total_pct)} | "
            f"{_pct(in_class)} | {_target(h)} | {_derived_in_class(layers, h)} |"
        )

    lines += ["", "## 3. Ações — consolidado", ""]
    if layers.stocks:
        stocks = layers.stocks
        lines += [
            f"As ações somam {_brl(stocks.value)}: {_pct(stocks.weight_total_pct)} do "
            f"patrimônio. Alvo derivado das ações: {_aggregate(stocks.target)}.",
            "",
            "| Ação | Valor | peso_total_pct | peso_classe_pct (dentro das ações) | "
            "Alvo (base A) | Alvo dentro das ações (derivado) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for h in stocks.holdings:
            lines.append(
                f"| {_label(h)} | {_brl(h.value)} | {_pct(h.weight_total_pct)} | "
                f"{_pct(stocks.weight_group_pct(h))} | {_target(h)} | "
                f"{_derived_in_class(layers, h)} |"
            )
    else:
        lines.append("Nenhuma ação no snapshot.")

    lines += ["", "## 4. Ações — por setor", ""]
    if layers.stock_sectors:
        lines += _group_table(layers.stock_sectors, "Setor")
        lines += [
            "",
            "Detalhe: `peso_setor_pct` é o peso do ativo dentro do setor.",
            "",
            *_detail_table(layers.stock_sectors, "Setor", "peso_setor_pct"),
        ]
    else:
        lines.append("Nenhuma ação no snapshot.")

    lines += ["", "## 5. Ações — por segmento", ""]
    if layers.stock_segments:
        lines += _group_table(layers.stock_segments, "Segmento", parent=True)
        lines += [
            "",
            "Detalhe: `peso_segmento_pct` é o peso do ativo dentro do segmento.",
            "",
            *_detail_table(layers.stock_segments, "Segmento", "peso_segmento_pct"),
        ]
    else:
        lines.append("Nenhuma ação no snapshot.")

    lines += ["", "## 6. FIIs — consolidado, tipo e segmento", ""]
    if layers.fiis:
        fiis = layers.fiis
        type_value = {g.label: g.value for g in layers.fii_types}
        segment_value = {g.label: g.value for g in layers.fii_segments}
        lines += [
            "Só os fundos imobiliários. FI-Infra e FIAgro são classes próprias (camadas 1 e "
            f"2). Os FIIs somam {_brl(fiis.value)}: {_pct(fiis.weight_total_pct)} do "
            f"patrimônio. Alvo derivado dos FIIs: {_aggregate(fiis.target)}.",
            "",
            "### Consolidado",
            "",
            "| Fundo | Tipo | Segmento | peso_total_pct | peso_classe_pct (dentro dos FIIs) | "
            "peso_tipo_pct | peso_segmento_pct | Alvo (base A) |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
        for h in fiis.holdings:
            lines.append(
                f"| `{h.id}` | {h.structure} | {h.segment} | {_pct(h.weight_total_pct)} | "
                f"{_pct(fiis.weight_group_pct(h))} | "
                f"{_pct(h.value / type_value[h.structure] * 100)} | "
                f"{_pct(h.value / segment_value[h.segment] * 100)} | {_target(h)} |"
            )
        lines += ["", "### Por tipo", "", *_group_table(layers.fii_types, "Tipo")]
        lines += [
            "",
            "### Por segmento",
            "",
            *_group_table(layers.fii_segments, "Segmento"),
        ]
    else:
        lines.append("Nenhum FII no snapshot.")

    lines += ["", "## Notas", ""]
    lines += [
        "- **Classificação:** o setor, o segmento e o tipo vêm do registro de ativos. "
        + (
            "Sem classificação no registro: "
            + ", ".join(f"`{i}`" for i in layers.unclassified)
            + " (aparecem no grupo `sem classificação`, nunca escondidos)."
            if layers.unclassified
            else "Todos os ativos das camadas 3 a 6 estão classificados."
        ),
        "- **Fora das camadas 3 a 6:** FI-Infra, FIAgro, ETF, FMP-FGTS e os CDBs só têm as "
        "camadas 1 e 2.",
        "- **Alvo derivado:** o alvo é definido UMA vez por ativo, na base A. A soma de um "
        "grupo só é total (`completo`) quando todos os ativos dele estão `definido`; até lá "
        "aparece `parcial` (o que já está definido) ou `pendente`. O alvo dentro da classe só "
        "aparece com a classe inteira definida.",
        "- **Limites por camada:** não existem. Classe, setor, segmento e tipo só têm "
        "visualização; limites agregados seriam uma evolução separada.",
        "",
    ]
    return "\n".join(lines)


def write_layers_report(
    vault_path: str | Path,
    layers: Layers,
    *,
    today: _dt.date,
    snapshot_date: _dt.date | None = None,
    policy_hash: str | None = None,
    policy_status: str | None = None,
) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_layers_report(
            layers,
            today=today,
            snapshot_date=snapshot_date,
            policy_hash=policy_hash,
            policy_status=policy_status,
        ),
        encoding="utf-8",
    )
    return path
