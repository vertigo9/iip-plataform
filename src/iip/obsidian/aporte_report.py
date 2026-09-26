"""A proposta de aporte do ciclo como nota do vault: ``02_Portfolio/Aporte_AAAA-MM.md`` (§12).

Gravada só por ``iip aporte-proposto --report`` -- comando manual, fora do job diário e de
qualquer agendador. O cabeçalho registra tudo o que reconstrói o conjunto exato de evidências
(datas da rodada, do ``Current.md`` e do snapshot de preço; os três hashes efetivamente
usados; universo, datas descartadas, fontes). É uma PROPOSTA: ``automatic_action`` é sempre
``"nenhuma"`` e ``aprovacao_da_proposta`` nasce ``pendente``; nada aqui é ordem.
"""

from __future__ import annotations

from pathlib import Path

from iip.obsidian.frontmatter import flow_line
from iip.portfolio.aporte import Proposal, report_relative_path


def _brl(value: float) -> str:
    text = f"{value:,.2f}"
    return "R$ " + text.replace(",", "_").replace(".", ",").replace("_", ".")


def _num(value: float, places: int) -> str:
    return f"{value:.{places}f}".replace(".", ",")


def render_aporte_report(
    proposal: Proposal,
) -> str:  # noqa: C901 - uma seção por parte do §12
    round_ = proposal.decision_round
    discarded = (
        [
            {"data": d.date, "problemas": [f"{line}:{why}" for line, why in d.problems]}
            for d in round_.discarded
        ]
        if round_
        else []
    )
    lines = [
        "---",
        "type: aporte_proposto",
        f"cycle: {proposal.cycle}",
        f"state: {proposal.state}",
        f"reason: {proposal.reason or ''}",
        flow_line("failed_preconditions", list(proposal.failed_preconditions)),
        f"decision_round_date: {round_.date if round_ and round_.date else ''}",
        f"current_snapshot_date: {proposal.current_snapshot_date or ''}",
        f"price_snapshot_date: {proposal.price_snapshot_date or ''}",
        "dias_entre_current_e_preco: "
        + ("" if proposal.date_gap_days is None else str(proposal.date_gap_days)),
        f"contract_hash: {proposal.contract_hash or ''}",
        f"target_policy_hash: {proposal.target_policy_hash or ''}",
        f"class_budget_hash: {proposal.class_budget_hash or ''}",
        f"universo_decisao: {round_.universe_size if round_ else ''}",
        f"dec_na_rodada: {len(round_.decisions) if round_ else 0}",
        flow_line("datas_descartadas", discarded),
        flow_line("fonte_current", proposal.current_snapshot_path),
        flow_line("fonte_precos", proposal.price_snapshot_path),
        f"orcamento: {proposal.budget:.2f}",
        f"soma_ideal: {proposal.sum_ideal:.2f}",
        f"soma_valor: {proposal.sum_value:.2f}",
        f"sobra_por_limite: {proposal.leftover_by_limit:.2f}",
        f"sobra_por_arredondamento: {proposal.leftover_by_rounding:.2f}",
        f"saldo_nao_alocado: {proposal.unallocated:.2f}",
        f"automatic_action: {proposal.automatic_action}",
        f"aprovacao_da_proposta: {proposal.proposal_approval}",
        "---",
        "",
        f"# Aporte proposto — {proposal.cycle}",
        "",
        f"**Estado: {proposal.state}**"
        + (f" ({proposal.reason})" if proposal.reason else "")
        + ". É uma proposta para aprovação humana: nada aqui é ordem, rebalanceamento ou "
        'movimentação financeira (`automatic_action: "nenhuma"`).',
        "",
    ]
    if proposal.failed_preconditions:
        lines += ["## Pré-condições que falharam", ""]
        lines += [f"- `{reason}`" for reason in proposal.failed_preconditions]
        lines.append("")
    if proposal.inconsistencies:
        lines += [
            f"## Inconsistências da reconciliação ({len(proposal.inconsistencies)})",
            "",
            "| Posição | Tipo | Detalhe |",
            "|---|---|---|",
        ]
        lines += [
            f"| `{inc.position_id}` | {inc.kind} | {inc.detail} |"
            for inc in proposal.inconsistencies
        ]
        lines.append("")
    if round_ is not None:
        lines += ["## Rodada de decisão", ""]
        if round_.date:
            lines.append(
                f"Rodada completa de {round_.date}: {len(round_.decisions)} DEC para "
                f"{round_.universe_size} linhas do universo, todas com score."
            )
        else:
            lines.append("Nenhuma rodada completa no ciclo.")
        for d in round_.discarded:
            problems = ", ".join(f"{line} ({why})" for line, why in d.problems)
            lines.append(f"- Descartada {d.date} (incompleta): {problems}")
        for note in round_.outside_universe:
            lines.append(f"- `{note.ticker}` decidido na rodada, fora do universo")
        lines.append("")
    if proposal.lines:
        lines += [
            "## Ranking e distribuição",
            "",
            "| # | Ativo | Veredito | I | G | OS | Ideal | Preço | Cotas | Valor |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for rank, ln in enumerate(proposal.lines, 1):
            lines.append(
                f"| {rank} | {ln.ticker} | {ln.verdict} | {_num(ln.decision_score, 2)} | "
                f"{_num(ln.gap, 4)} | {_num(ln.opportunity_score, 4)} | {_brl(ln.ideal)} | "
                f"{_brl(ln.price)} | {ln.shares} | {_brl(ln.value)} |"
            )
        lines += [
            "",
            f"Σ ideal {_brl(proposal.sum_ideal)} · Σ valor {_brl(proposal.sum_value)} · "
            f"sobra por limite {_brl(proposal.leftover_by_limit)} · sobra por arredondamento "
            f"{_brl(proposal.leftover_by_rounding)} · saldo não alocado "
            f"{_brl(proposal.unallocated)} (nunca redistribuído).",
            "",
        ]
    if proposal.exclusions:
        lines += [
            f"## Exclusões ({len(proposal.exclusions)})",
            "",
            "| Linha | Ativo | Motivo | Detalhe |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| `{exc.line_id}` | {exc.ticker} | {exc.reason} | {exc.detail} |"
            for exc in proposal.exclusions
        ]
        lines.append("")
    return "\n".join(lines)


def write_aporte_report(vault_path: str | Path, proposal: Proposal) -> Path:
    path = Path(vault_path) / report_relative_path(proposal.cycle)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_aporte_report(proposal), encoding="utf-8")
    return path
