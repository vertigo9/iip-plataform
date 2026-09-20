"""A política de pesos-alvo como nota do vault: ``02_Portfolio/Politica_Pesos_Alvo.md``.

Sobrescrita a cada execução. É a tabela de decisão por ativo: peso atual (base A), alvo,
tolerância, mínimo, máximo e status, mais a reconciliação com o snapshot e as regras do modelo.
O peso atual é INFORMAÇÃO, não sugestão de alvo. Nada aqui é ordem de compra, venda, aporte ou
rebalanceamento.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from iip.obsidian.frontmatter import flow_line
from iip.portfolio.target_policy import Reconciliation, TargetPolicy

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Politica_Pesos_Alvo.md"

_SUM_RULE_TEXT = {
    None: "em aberto (decisão do usuário)",
    "total_100": "os alvos somam 100%",
    "reserva": "parte fica sem alvo, como reserva de oportunidade",
}


def _brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}".replace(".", ",") + "%"


def _pp(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}".replace(".", ",") + " p.p."


def _frontmatter(
    policy: TargetPolicy, rec: Reconciliation, today: _dt.date
) -> list[str]:
    statuses: dict[str, int] = {}
    for line in policy.lines:
        statuses[line.status] = statuses.get(line.status, 0) + 1
    return [
        "---",
        "type: target_weight_policy_note",
        f"date: {today.isoformat()}",
        f"politica_versao: {policy.version}",
        f"politica_hash: {policy.content_hash}",
        f"politica_status: {policy.approval_status}",
        f"monitoramento_ativo: {str(policy.monitoring_enabled).lower()}",
        flow_line("regra_de_soma", policy.sum_rule),
        flow_line("linhas", len(policy.lines)),
        flow_line("linhas_por_status", statuses),
        flow_line("posicoes_sem_linha", [r.id for r in rec.uncovered]),
        flow_line("linhas_sem_posicao", [ln.id for ln in rec.absent_lines]),
        "---",
    ]


def render_policy_report(
    policy: TargetPolicy, rec: Reconciliation, today: _dt.date
) -> str:
    approved = policy.approval_status == "aprovada"
    lines = [
        *_frontmatter(policy, rec, today),
        "",
        "# Política de pesos-alvo por ativo",
        "",
        f"Política **{policy.approval_status}** (versão {policy.version}, hash "
        f"{policy.content_hash}), dados de {today:%d/%m/%Y}. É uma camada de POLÍTICA: "
        "define o que você quer e mede o desvio; não compra, vende, aporta nem rebalanceia, e "
        "não decide nada sozinha. O peso atual abaixo é informação, não sugestão de alvo.",
        "",
        "## Situação",
        "",
        f"- **Base de cálculo {policy.base_id}**: {policy.base_description}; "
        f"{_brl(rec.total)} no snapshot atual.",
        f"- **Soma dos alvos**: {_SUM_RULE_TEXT[policy.sum_rule]}.",
        f"- **Monitoramento** (sinalizar qualquer saída da faixa): "
        f"{'LIGADO' if policy.monitoring_enabled else 'desligado'}"
        f"{'' if approved else ' até a política ser aprovada'}.",
        "- **Execução**: nenhuma. Aportes e rebalanceamentos não estão autorizados por esta "
        "política.",
        "",
        "## Decisões já tomadas",
        "",
        "- Granularidade por ativo; modelo alvo + faixa de tolerância + limites mínimo e "
        "máximo individuais.",
        "- Base A. CDBs agrupados numa linha de renda fixa bancária (os registros individuais "
        "ficam como composição); LFTB11 e FMP-FGTS são ativos próprios.",
        "- `FMP-FGTS-DAYCOVAL` é o identificador canônico do fundo e `AXIA3` é o apelido "
        "legado do registro (o fundo, não a ação AXIA3, que não está na carteira).",
        "",
        "## Tabela de decisão por ativo",
        "",
        "Os campos vazios (—) são seus: nenhum percentual foi preenchido pelo IIP.",
        "",
        "| Linha | Classe | Composição | Valor | Peso atual (base A) | Alvo | Tolerância | "
        "Mínimo | Máximo | Status |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in sorted(rec.weights, key=lambda w: -w.weight_pct):
        line = item.line
        if line.kind == "group":
            composition = f"{len(item.present)} de {len(line.members)} registros"
        elif line.aliases:
            composition = f"apelido legado: {', '.join(line.aliases)}"
        else:
            composition = "—"
        lines.append(
            f"| `{line.id}` {'' if line.name == line.id else '· ' + line.name} | "
            f"{line.asset_class} | {composition} | {_brl(item.value)} | "
            f"{_pct(item.weight_pct)} | {_pct(line.target_pct)} | {_pp(line.tolerance_pp)} | "
            f"{_pct(line.min_pct)} | {_pct(line.max_pct)} | {line.status} |"
        )
    lines += ["", "## Reconciliação com o snapshot", ""]
    if rec.consistent and not rec.missing_members:
        lines.append(
            "A política e o snapshot batem: toda posição tem linha e toda linha ativa tem "
            "posição."
        )
    else:
        for row in rec.uncovered:
            lines.append(
                f"- **Posição sem linha na política**: `{row.id}` ({_brl(row.value)}): "
                "precisa de uma linha ou de ser registrada como zerada."
            )
        for line in rec.absent_lines:
            lines.append(
                f"- **Linha sem posição no snapshot**: `{line.id}`: zerada? marque como "
                "`inativo` ou mova para `retired`."
            )
        for row in rec.reopened:
            lines.append(
                f"- **Posição registrada como zerada aparece no snapshot**: `{row.id}` "
                f"({_brl(row.value)})."
            )
        for group, member in rec.missing_members:
            lines.append(f"- Registro de `{group}` que saiu do snapshot: `{member}`.")
        for group, row in rec.new_members:
            lines.append(
                f"- Registro novo em `{group}`: `{row.id}` ({_brl(row.value)}), contado no "
                "grupo mas ainda fora de `members`."
            )
    lines += ["", "### Posições zeradas (fora do universo ativo)", ""]
    for retired in policy.retired:
        lines.append(f"- `{retired.id}`: zerada em {retired.closed_on}. {retired.note}")
    if not policy.retired:
        lines.append("Nenhuma.")
    lines += [
        "",
        "## Regras do modelo",
        "",
        "- `mínimo <= alvo <= máximo`, e a faixa `alvo ± tolerância` cabe dentro de "
        "`[mínimo, máximo]`: a tolerância dispara o sinal, o limite é o teto rígido.",
        "- Uma linha `definido` tem alvo, tolerância, mínimo, máximo e data da decisão. Os "
        "status são `pendente`, `definido`, `revisavel` e `inativo`.",
        "- A soma dos alvos definidos nunca passa de 100%. A política só vira `aprovada` com "
        "todas as linhas ativas `definido` e a regra de soma escolhida e cumprida; só então "
        "o monitoramento pode ligar.",
        "- Erros de configuração (JSON inválido, chave desconhecida, números incoerentes) "
        "param o comando com o motivo; nunca há valor padrão silencioso.",
        "",
        "## Como preencher",
        "",
        "Edite `02_Portfolio/Politica_Pesos_Alvo.json` (campos `target_pct`, `tolerance_pp`, "
        "`min_pct`, `max_pct`, `status`, `rationale`, `decided_on`) ou passe os valores ao "
        "assistente. Rode `iip target-policy --report` para validar e atualizar esta nota.",
        "",
    ]
    return "\n".join(lines)


def write_policy_report(
    vault_path: str | Path,
    policy: TargetPolicy,
    rec: Reconciliation,
    today: _dt.date,
) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_policy_report(policy, rec, today), encoding="utf-8")
    return path
