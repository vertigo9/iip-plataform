"""Aporte proposto (APORTE_PROPOSTO_V1, revisão 4): gera a PROPOSTA mensal de distribuição do
orçamento de aporte entre as posições elegíveis. Nunca executa nada.

Contrato vinculante: ``aporte_contract.py`` (texto aprovado em 26/09/2026, SHA-256
``63bbeda126534b80716bf4b477bedc1d530db4c44d09dea2e47f91ebc905f7a0``). As seções citadas
(§3.1, §4, ...) são as do contrato.

Camada nova, que só LÊ: a política de pesos-alvo e o orçamento por classe (``target_policy``,
``class_budget``), as notas ``DEC-*`` já gravadas pelo ``decide-portfolio`` (veredito e
``decision_score``), o ``Current.md`` e o snapshot diário de preços do ``refresh-portfolio``.
Não importa o motor de decisão nem recalcula score: o ``I`` é sempre o ``decision_score``
gravado na nota (§2 ``decision_score_persistence = required``). Não importa os módulos antigos
de aporte/oportunidade (``integration``, ``portfolio_decision``, ``strategy``,
``orchestration``): há teste de importação.

O cálculo (``build_proposal``) é puro -- recebe os dados já lidos e devolve a proposta; a
leitura do vault fica nas funções ``read_*`` / ``load_inputs``. Dado ausente nunca é
completado: sem ele, a linha sai com motivo ou a proposta sai ``VAZIA``.

``automatic_action`` é sempre ``"nenhuma"``; nenhum estado da proposta significa execução, e
cada proposta mensal tem aprovação humana própria (``aprovacao_da_proposta: pendente``).
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from iip.knowledge.models import Verdict
from iip.knowledge.repository import ObsidianRepository
from iip.portfolio.aporte_contract import (
    AUTOMATIC_ACTION,
    SNAPSHOT_DATE_BASIS_ORDER,
    AporteContract,
    load_contract,
)
from iip.portfolio.class_budget import ClassBudget, load_budget
from iip.portfolio.evidence_lookup import _frontmatter
from iip.portfolio.target_policy import (
    SNAPSHOT_RELATIVE_PATH,
    PolicyLine,
    Reconciliation,
    SnapshotRow,
    TargetPolicy,
    load_policy,
    read_snapshot_rows,
    reconcile,
)

DECISIONS_DIR = "03_Decisions"
REPORT_DIR = Path("02_Portfolio")

STATE_COMPLETE = "COMPLETA"
STATE_PARTIAL = "PARCIALMENTE_ALOCADA"
STATE_EMPTY = "VAZIA"

# Motivos de VAZIA (§4, §11). A ordem é a do §4: o primeiro que falha é o motivo da proposta.
REASON_CONTRACT = "contrato_nao_aprovado"
REASON_POLICY = "politica_nao_aprovada"
REASON_BUDGET = "orcamento_classe_nao_aprovado"
REASON_NO_ROUND = "sem_rodada_completa_no_ciclo"
REASON_NO_PRICE_SNAPSHOT = "sem_snapshot_de_preco_no_ciclo"
REASON_RECONCILIATION = "reconciliacao_inconsistente"
# Motivos temporais do Current.md (rev. 4.1 §8.1), NESTA ordem normativa: só o primeiro
# aplicável é registrado.
REASON_CURRENT_DATE_MISSING = "current_snapshot_date_missing"
REASON_CURRENT_BASIS_MISSING = "current_snapshot_basis_missing"
REASON_CURRENT_CAPTURE_MISSING = "current_snapshot_capture_missing"
REASON_CURRENT_DATE_INCONSISTENT = "current_snapshot_date_inconsistent"
REASON_CURRENT_OUT_OF_CYCLE = "current_snapshot_fora_do_ciclo"
BASIS_CAPTURE_DATE = "capture_date"
CAPTURE_DATE_WARNING = "Data de captura, não data declarada pela fonte."
REASON_NO_ELIGIBLE = "nenhum_elegivel"

# Exclusões individuais (§5), na ordem em que são testadas.
EXCL_VETOED = "veredito_vetado"
EXCL_NO_POSITION = "sem_posicao_no_current"
EXCL_CLASS_DIVERGENT = "classe_divergente"
EXCL_AT_TARGET = "no_ou_acima_do_alvo"
EXCL_NO_PRICE = "sem_preco_no_ciclo"
EXCL_CLASS_NOT_BUDGETED = "classe_fora_do_orcamento"

# Por que uma data do ciclo não é rodada completa (§3.1), por linha do universo.
ROUND_MISSING = "sem_dec"
ROUND_DUPLICATED = "dec_duplicada"
ROUND_NO_SCORE = "sem_score"
ROUND_BAD_VERDICT = "veredito_invalido"

# Inconsistências estruturais que bloqueiam (§4.6, lista fechada).
INCONS_UNRESOLVED = "posicao_sem_linha_na_politica"
INCONS_REOPENED = "posicao_encerrada_ativa_no_current"
INCONS_NEW_MEMBER = "posicao_fora_dos_membros_do_grupo"

_CYCLE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EPS = 1e-6  # tolerância monetária (R$) nas comparações de invariantes e estados


class AporteInvariantError(ValueError):
    """Um invariante do §10 falhou: a proposta é rejeitada, nada é gravado."""


# --- entradas ------------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionNote:
    """O que a proposta usa de uma nota ``DEC-*``: só o que está gravado nela."""

    ticker: str
    date: str  # AAAA-MM-DD, do cabeçalho da nota
    verdict: str  # vocabulário do conhecimento (new_verdict)
    score: (
        float | None
    )  # decision_score gravado; None se ausente ou não numérico/finito
    source: str = ""  # nome do arquivo, para rastreabilidade


@dataclass(frozen=True)
class SnapshotProvenance:
    """A proveniência temporal gravada no cabeçalho do ``Current.md`` (rev. 4.1), como texto
    cru. ``processed_at`` e o mtime do arquivo não entram aqui de propósito: não têm
    autoridade temporal (§3, §10)."""

    snapshot_date: str | None = None
    basis: str | None = None  # snapshot_date_basis
    evidence: str | None = None  # snapshot_date_evidence
    captured_at: str | None = None


@dataclass(frozen=True)
class AporteInputs:
    cycle: str  # AAAA-MM
    contract: AporteContract | None
    policy: TargetPolicy | None
    budget: ClassBudget | None
    rows: tuple[SnapshotRow, ...]
    current_provenance: SnapshotProvenance
    decisions: tuple[DecisionNote, ...]
    price_snapshot_date: _dt.date | None  # None = nenhuma pasta de snapshot no ciclo
    prices: Mapping[str, float | None]  # ticker -> preço do snapshot do ciclo
    current_snapshot_path: str = ""
    price_snapshot_path: str = ""


# --- saídas --------------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscardedDate:
    """Uma data do ciclo, mais recente que a rodada escolhida, que não é rodada completa."""

    date: str
    problems: tuple[tuple[str, str], ...]  # (linha, motivo ROUND_*)


@dataclass(frozen=True)
class DecisionRound:
    date: str | None
    decisions: Mapping[str, DecisionNote]  # linha da política -> DEC da rodada
    discarded: tuple[DiscardedDate, ...]
    outside_universe: tuple[
        DecisionNote, ...
    ]  # DEC da rodada de ticker fora do universo
    universe_size: int


@dataclass(frozen=True)
class Inconsistency:
    kind: str  # INCONS_*
    position_id: str
    detail: str


@dataclass(frozen=True)
class Exclusion:
    line_id: str
    ticker: str
    reason: str  # EXCL_*
    detail: str = ""


@dataclass(frozen=True)
class ProposalLine:
    line_id: str
    ticker: str
    asset_class: str
    verdict: str
    decision_score: float  # I
    gap: float  # G
    opportunity_score: float  # OS
    weight_pct: float
    target_pct: float
    cap_asset: float
    price: float
    ideal: float = 0.0
    shares: int = 0
    value: float = 0.0
    decision_date: str = ""
    price_snapshot_date: str = ""


@dataclass(frozen=True)
class Proposal:
    cycle: str
    state: str
    reason: str | None  # motivo do VAZIA (o primeiro que falhou)
    failed_preconditions: tuple[str, ...]
    budget: float
    lines: tuple[ProposalLine, ...] = ()
    exclusions: tuple[Exclusion, ...] = ()
    inconsistencies: tuple[Inconsistency, ...] = ()
    decision_round: DecisionRound | None = None
    current_snapshot_date: str | None = None
    snapshot_date_basis: str | None = None
    snapshot_date_evidence: str | None = None
    captured_at: str | None = None
    price_snapshot_date: str | None = None
    contract_hash: str | None = None
    target_policy_hash: str | None = None
    class_budget_hash: str | None = None
    current_snapshot_path: str = ""
    price_snapshot_path: str = ""
    class_caps: Mapping[str, float] = field(default_factory=dict)
    automatic_action: str = AUTOMATIC_ACTION
    proposal_approval: str = "pendente"

    @property
    def sum_ideal(self) -> float:
        return sum(ln.ideal for ln in self.lines)

    @property
    def sum_value(self) -> float:
        return round(sum(ln.value for ln in self.lines), 2)

    @property
    def leftover_by_limit(self) -> float:
        return self.budget - self.sum_ideal

    @property
    def leftover_by_rounding(self) -> float:
        return self.sum_ideal - self.sum_value

    @property
    def unallocated(self) -> float:
        return self.leftover_by_limit + self.leftover_by_rounding

    @property
    def date_gap_days(self) -> int | None:
        if self.current_snapshot_date is None or self.price_snapshot_date is None:
            return None
        return (
            _dt.date.fromisoformat(self.price_snapshot_date)
            - _dt.date.fromisoformat(self.current_snapshot_date)
        ).days


# --- proveniência temporal do Current.md (rev. 4.1) ---------------------------------------


def _iso_date(raw: str | None) -> _dt.date | None:
    """Só ``AAAA-MM-DD`` exato; qualquer outra coisa é inválida (nada é completado)."""
    if raw is None or not _DATE_RE.match(raw.strip()):
        return None
    try:
        return _dt.date.fromisoformat(raw.strip())
    except ValueError:
        return None


def captured_local_date(raw: str | None) -> _dt.date | None:
    """A data LOCAL de ``captured_at`` (§5): com hora, o fuso é obrigatório e a data é a do fuso
    declarado (nunca convertida para UTC); só com data, é usada literalmente. Inválido ou hora
    sem fuso -> ``None``."""
    if raw is None or not raw.strip():
        return None
    text = raw.strip()
    if "T" not in text:
        return _iso_date(text)
    if not _DATE_RE.match(text[:10]):
        return None
    try:
        moment = _dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None or moment.utcoffset() is None:
        return None
    return moment.date()


def check_snapshot_provenance(
    prov: SnapshotProvenance,
    cycle: str,
    basis_order: tuple[str, ...] = SNAPSHOT_DATE_BASIS_ORDER,
) -> tuple[_dt.date | None, str | None]:
    """A ``snapshot_date`` comprovada e o PRIMEIRO motivo temporal aplicável, na ordem
    normativa do §8.1 (``None`` se passou). Pura; nunca usa mtime, ``processed_at`` nem a data
    do sistema. A precedência entre as bases é garantia do procedimento de captura, não daqui:
    este teste só confere que a base registrada pertence ao vocabulário e cumpre as regras
    dela."""
    snapshot_date = _iso_date(prov.snapshot_date)
    if snapshot_date is None:
        return None, REASON_CURRENT_DATE_MISSING
    if (
        prov.basis not in basis_order
        or prov.evidence is None
        or not prov.evidence.strip()
    ):
        return snapshot_date, REASON_CURRENT_BASIS_MISSING
    has_capture = prov.captured_at is not None and bool(prov.captured_at.strip())
    captured = captured_local_date(prov.captured_at)
    if prov.basis == BASIS_CAPTURE_DATE:
        if captured is None:
            return snapshot_date, REASON_CURRENT_CAPTURE_MISSING
        if snapshot_date != captured:
            return snapshot_date, REASON_CURRENT_DATE_INCONSISTENT
    elif has_capture and (captured is None or snapshot_date > captured):
        return snapshot_date, REASON_CURRENT_DATE_INCONSISTENT
    if snapshot_date.isoformat()[:7] != cycle:
        return snapshot_date, REASON_CURRENT_OUT_OF_CYCLE
    return snapshot_date, None


# --- universo e rodada completa (§3, §3.1) -------------------------------------------------


def decision_universe(policy: TargetPolicy) -> tuple[PolicyLine, ...]:
    """Linhas ``kind = asset`` com status ≠ ``inativo``. Grupos e posições encerradas
    (``retired``, que não são linhas) ficam fora por definição."""
    return tuple(
        ln for ln in policy.lines if ln.kind == "asset" and ln.status != "inativo"
    )


def _line_of(universe: tuple[PolicyLine, ...], ticker: str) -> PolicyLine | None:
    return next((ln for ln in universe if ticker in (ln.id, *ln.aliases)), None)


def find_decision_round(
    policy: TargetPolicy, decisions: tuple[DecisionNote, ...], cycle: str
) -> DecisionRound:
    """A data mais recente do ciclo em que cada linha do universo tem exatamente uma DEC
    daquela data, com ``decision_score`` finito e veredito do vocabulário do conhecimento.
    Sem fallback de ativo: se a data mais recente está incompleta, a rodada inteira passa para
    a data completa anterior do MESMO ciclo; nenhuma completa -> ``date = None``. A
    completude é sempre contra a política passada (a vigente), nunca contra a da época das
    DEC."""
    universe = decision_universe(policy)
    known = {v.value for v in Verdict}
    by_date: dict[str, list[DecisionNote]] = defaultdict(list)
    for note in decisions:
        if note.date[:7] == cycle:
            by_date[note.date].append(note)
    discarded: list[DiscardedDate] = []
    for date in sorted(by_date, reverse=True):
        notes = by_date[date]
        chosen: dict[str, DecisionNote] = {}
        problems: list[tuple[str, str]] = []
        for line in universe:
            matches = [n for n in notes if n.ticker in (line.id, *line.aliases)]
            if not matches:
                problems.append((line.id, ROUND_MISSING))
            elif len(matches) > 1:
                problems.append((line.id, ROUND_DUPLICATED))
            elif matches[0].verdict not in known:
                problems.append((line.id, ROUND_BAD_VERDICT))
            elif matches[0].score is None or not math.isfinite(matches[0].score):
                problems.append((line.id, ROUND_NO_SCORE))
            else:
                chosen[line.id] = matches[0]
        if problems:
            discarded.append(DiscardedDate(date, tuple(problems)))
            continue
        outside = tuple(
            sorted(
                (n for n in notes if _line_of(universe, n.ticker) is None),
                key=lambda n: n.ticker,
            )
        )
        return DecisionRound(date, chosen, tuple(discarded), outside, len(universe))
    return DecisionRound(None, {}, tuple(discarded), (), len(universe))


# --- reconciliação (§4.6) ------------------------------------------------------------------


@dataclass(frozen=True)
class ReconciliationSplit:
    """A reconciliação separada nas duas consequências que o contrato distingue (§4.6, §5):

    - ``blocking``: SÓ ``uncovered``, ``reopened`` e ``new_members`` -- bloqueiam a proposta
      inteira (``reconciliacao_inconsistente``);
    - ``absent_line_ids``: linhas ativas sem posição no ``Current.md`` -- NUNCA bloqueiam; cada
      uma vira a exclusão individual ``sem_posicao_no_current`` (§5), sem peso inferido.

    ``Reconciliation.consistent`` mistura as duas coisas (conta ``absent_lines``) e não é usado
    em nenhum caminho do aporte (há teste de AST)."""

    blocking: tuple[Inconsistency, ...]
    absent_line_ids: tuple[str, ...]


def split_reconciliation(rec: Reconciliation) -> ReconciliationSplit:
    return ReconciliationSplit(
        blocking_inconsistencies(rec),
        tuple(sorted(ln.id for ln in rec.absent_lines)),
    )


def blocking_inconsistencies(rec: Reconciliation) -> tuple[Inconsistency, ...]:
    """Só a lista fechada do §4.6 (``uncovered``, ``reopened``, ``new_members``). Não olha
    ``absent_lines`` nem ``missing_members``: ausência de posição não é inconsistência.
    """
    found = [
        Inconsistency(
            INCONS_UNRESOLVED,
            row.id,
            f"{row.name} ({row.asset_class}) não resolve para nenhuma linha por id/alias/membro",
        )
        for row in rec.uncovered
    ]
    found += [
        Inconsistency(
            INCONS_REOPENED,
            row.id,
            f"{row.name}: encerrada na política (retired) e ativa no Current.md",
        )
        for row in rec.reopened
    ]
    found += [
        Inconsistency(
            INCONS_NEW_MEMBER,
            row.id,
            f"{row.name} ({row.asset_class}) não está entre os membros do grupo {group}",
        )
        for group, row in rec.new_members
    ]
    return tuple(found)


# --- a proposta ----------------------------------------------------------------------------


def _provenance_fields(inputs: AporteInputs) -> dict:
    """O que o relatório preserva da proveniência (rev. 4.1 §12): a data só quando é uma data
    válida; base, evidência e captura como gravadas."""
    prov = inputs.current_provenance
    snapshot_date = _iso_date(prov.snapshot_date)
    return {
        "current_snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
        "snapshot_date_basis": prov.basis,
        "snapshot_date_evidence": prov.evidence,
        "captured_at": prov.captured_at,
    }


def _empty(
    inputs: AporteInputs, reason: str, failed: tuple[str, ...] = (), **extra
) -> Proposal:
    contract = inputs.contract
    return Proposal(
        cycle=inputs.cycle,
        state=STATE_EMPTY,
        reason=reason,
        failed_preconditions=failed,
        budget=contract.monthly_budget_brl if contract else 0.0,
        **_provenance_fields(inputs),
        price_snapshot_date=(
            inputs.price_snapshot_date.isoformat()
            if inputs.price_snapshot_date
            else None
        ),
        contract_hash=contract.content_hash if contract else None,
        target_policy_hash=inputs.policy.content_hash if inputs.policy else None,
        class_budget_hash=inputs.budget.content_hash if inputs.budget else None,
        current_snapshot_path=inputs.current_snapshot_path,
        price_snapshot_path=inputs.price_snapshot_path,
        **extra,
    )


def _in_cycle(date: _dt.date | None, cycle: str) -> bool:
    return date is not None and date.isoformat()[:7] == cycle


def build_proposal(
    inputs: AporteInputs,
) -> Proposal:  # noqa: C901 - segue o contrato passo a passo
    """A proposta do ciclo. Pura: não lê nem grava nada. Levanta ``AporteInvariantError`` se
    um invariante do §10 falhar (proposta rejeitada)."""
    if not _CYCLE_RE.match(inputs.cycle):
        raise ValueError(f"ciclo {inputs.cycle!r} não é AAAA-MM")
    contract, policy, budget = inputs.contract, inputs.policy, inputs.budget

    # §4 -- pré-condições, na ordem; todas avaliadas, a primeira que falha é o motivo
    failed: list[str] = []
    if (
        contract is None
        or contract.approval_status != "aprovada"
        or contract.automatic_action != AUTOMATIC_ACTION
    ):
        failed.append(REASON_CONTRACT)
    if policy is None or policy.approval_status != "aprovada":
        failed.append(REASON_POLICY)
    if budget is None or budget.approval_status != "aprovada":
        failed.append(REASON_BUDGET)
    round_ = (
        find_decision_round(policy, inputs.decisions, inputs.cycle)
        if policy is not None
        else None
    )
    if round_ is None or round_.date is None:
        failed.append(REASON_NO_ROUND)
    if not _in_cycle(inputs.price_snapshot_date, inputs.cycle):
        failed.append(REASON_NO_PRICE_SNAPSHOT)
    # Reconciliação: só os três bloqueios globais contam. Um Current.md sem posições (ou sem
    # a linha X) não é inconsistência: vira exclusão individual adiante; a falta do arquivo
    # já aparece como motivo temporal (current_snapshot_date_missing).
    rec = reconcile(policy, inputs.rows) if policy is not None else None
    split = split_reconciliation(rec) if rec is not None else None
    inconsistencies = split.blocking if split is not None else ()
    if inconsistencies:
        failed.append(REASON_RECONCILIATION)
    # §4.7 + rev. 4.1 §8.1: no máximo UM motivo temporal, o primeiro na ordem normativa
    _, temporal_reason = check_snapshot_provenance(
        inputs.current_provenance,
        inputs.cycle,
        contract.snapshot_date_basis_order if contract else SNAPSHOT_DATE_BASIS_ORDER,
    )
    if temporal_reason is not None:
        failed.append(temporal_reason)
    if failed:
        return _empty(
            inputs,
            failed[0],
            tuple(failed),
            decision_round=round_,
            inconsistencies=inconsistencies,
        )
    assert contract is not None and policy is not None and budget is not None
    assert round_ is not None and rec is not None and split is not None

    total = rec.total
    weight_by_line = {lw.line.id: lw for lw in rec.weights}
    # posições de cada linha pelo MESMO critério do reconcile (policy.resolve: id, alias ou
    # membro), sem depender de ids únicos no Current.md
    rows_by_line: dict[str, list[SnapshotRow]] = defaultdict(list)
    for row in inputs.rows:
        resolved = policy.resolve(row.id)
        if resolved is not None:
            rows_by_line[resolved.id].append(row)
    class_weight: dict[str, float] = defaultdict(float)
    for lw in rec.weights:  # §8: peso da classe agregado pela classe da POLÍTICA
        class_weight[lw.line.asset_class] += lw.weight_pct
    budget_lines = {
        ln.class_id: ln
        for ln in budget.lines
        if ln.status == "definido" and ln.target_pct is not None
    }
    class_caps = {
        class_id: max(
            (ln.target_pct - class_weight.get(class_id, 0.0)) / 100 * total, 0.0
        )
        for class_id, ln in budget_lines.items()
    }
    price_date = inputs.price_snapshot_date.isoformat()

    # §5 -- elegibilidade, sobre o universo (cada linha tem exatamente uma DEC da rodada)
    candidates: list[ProposalLine] = []
    exclusions: list[Exclusion] = []
    for line in decision_universe(policy):
        note = round_.decisions[line.id]
        lw = weight_by_line[line.id]
        if note.verdict not in contract.eligible_verdicts:
            exclusions.append(
                Exclusion(line.id, note.ticker, f"{EXCL_VETOED}:{note.verdict}")
            )
            continue
        positions = rows_by_line.get(line.id, [])
        if line.id in split.absent_line_ids or not positions:
            # §5.2: exclusão individual; o peso 0 do reconcile NUNCA é usado como dado
            exclusions.append(Exclusion(line.id, note.ticker, EXCL_NO_POSITION))
            continue
        # §5.3: basta UMA posição da linha (id ou alias) com classe diferente da política;
        # o detalhe é ordenado, então a ordem das linhas do Current.md não muda o resultado
        divergent = sorted(
            f"{row.id}={row.asset_class}"
            for row in positions
            if row.asset_class != line.asset_class
        )
        if divergent:
            exclusions.append(
                Exclusion(
                    line.id,
                    note.ticker,
                    EXCL_CLASS_DIVERGENT,
                    f"política: {line.asset_class}; Current.md: {', '.join(divergent)}",
                )
            )
            continue
        target = line.target_pct
        if target is None or lw.weight_pct >= target:
            exclusions.append(
                Exclusion(
                    line.id,
                    note.ticker,
                    EXCL_AT_TARGET,
                    f"peso {lw.weight_pct:.4f}% / alvo {target}%",
                )
            )
            continue
        price = inputs.prices.get(note.ticker)
        if price is None or not math.isfinite(price) or price <= 0:
            exclusions.append(Exclusion(line.id, note.ticker, EXCL_NO_PRICE))
            continue
        if line.asset_class not in budget_lines:
            exclusions.append(
                Exclusion(
                    line.id, note.ticker, EXCL_CLASS_NOT_BUDGETED, line.asset_class
                )
            )
            continue
        gap = min(max((target - lw.weight_pct) / target, 0.0), 1.0)
        score = note.score
        assert score is not None
        candidates.append(
            ProposalLine(
                line_id=line.id,
                ticker=note.ticker,
                asset_class=line.asset_class,
                verdict=note.verdict,
                decision_score=score,
                gap=gap,
                opportunity_score=score
                * (contract.intrinsic_weight + contract.gap_weight * gap),
                weight_pct=lw.weight_pct,
                target_pct=target,
                cap_asset=(target - lw.weight_pct) / 100 * total,
                price=price,
                decision_date=note.date,
                price_snapshot_date=price_date,
            )
        )

    common = {
        "decision_round": round_,
        "inconsistencies": inconsistencies,
        "exclusions": tuple(exclusions),
        "class_caps": class_caps,
    }
    if not candidates:
        return _empty(inputs, REASON_NO_ELIGIBLE, **common)

    # §7 -- ranking: OS ↓, I ↓, ticker ↑ (precisão total)
    candidates.sort(key=lambda c: (-c.opportunity_score, -c.decision_score, c.ticker))

    # §9 -- distribuição gulosa: ideal em R$, depois cotas inteiras; sobra nunca redistribuída
    remaining = contract.monthly_budget_brl
    class_remaining = dict(class_caps)
    monthly_cap = contract.monthly_asset_cap_brl
    lines: list[ProposalLine] = []
    for cand in candidates:
        ideal = max(
            min(
                remaining,
                cand.cap_asset,
                monthly_cap,
                class_remaining[cand.asset_class],
            ),
            0.0,
        )
        shares = math.floor(round(ideal / cand.price, 9))
        value = round(shares * cand.price, 2)
        remaining -= ideal
        class_remaining[cand.asset_class] -= ideal
        lines.append(replace(cand, ideal=ideal, shares=shares, value=value))

    sum_ideal = sum(ln.ideal for ln in lines)
    state = (
        STATE_COMPLETE
        if abs(sum_ideal - contract.monthly_budget_brl) <= _EPS
        else STATE_PARTIAL
    )
    proposal = Proposal(
        cycle=inputs.cycle,
        state=state,
        reason=None,
        failed_preconditions=(),
        budget=contract.monthly_budget_brl,
        lines=tuple(lines),
        **_provenance_fields(inputs),
        price_snapshot_date=price_date,
        contract_hash=contract.content_hash,
        target_policy_hash=policy.content_hash,
        class_budget_hash=budget.content_hash,
        current_snapshot_path=inputs.current_snapshot_path,
        price_snapshot_path=inputs.price_snapshot_path,
        **common,
    )
    check_invariants(proposal, policy, budget, rec, contract)
    return proposal


# --- invariantes (§10) ---------------------------------------------------------------------


def check_invariants(  # noqa: C901 - um bloco por invariante
    proposal: Proposal,
    policy: TargetPolicy,
    budget: ClassBudget,
    rec: Reconciliation,
    contract: AporteContract,
) -> None:
    """Levanta ``AporteInvariantError`` no primeiro invariante que falhar."""

    def broken(number: int, detail: str) -> AporteInvariantError:
        return AporteInvariantError(f"invariante {number} do §10 falhou: {detail}")

    total = rec.total
    monthly_cap = contract.monthly_asset_cap_brl
    if proposal.sum_value > proposal.budget + _EPS:  # 1
        raise broken(1, f"Σ valor {proposal.sum_value} > orçamento {proposal.budget}")
    for ln in proposal.lines:  # 2
        if not (
            ln.value <= ln.ideal + _EPS
            and ln.ideal <= min(ln.cap_asset, monthly_cap) + _EPS
        ):
            raise broken(2, f"{ln.ticker}: valor {ln.value}, ideal {ln.ideal}")
    ideal_by_class: dict[str, float] = defaultdict(float)
    for ln in proposal.lines:
        ideal_by_class[ln.asset_class] += ln.ideal
    for class_id, amount in ideal_by_class.items():  # 3
        if amount > proposal.class_caps.get(class_id, 0.0) + _EPS:
            raise broken(3, f"classe {class_id}: Σ ideal {amount} > cap_classe")
    weights = {lw.line.id: lw for lw in rec.weights}
    for ln in proposal.lines:  # 4 -- base: o total antes do aporte (a mesma dos caps)
        projected = weights[ln.line_id].value + ln.ideal
        if projected > ln.target_pct / 100 * total + _EPS:
            raise broken(4, f"{ln.ticker} projetado acima do alvo individual")
    proposed = {ln.line_id for ln in proposal.lines}
    for exc in proposal.exclusions:  # 5
        if exc.line_id in proposed:
            raise broken(5, f"{exc.line_id} excluído e com valor")
    class_value: dict[str, float] = defaultdict(float)
    for lw in rec.weights:
        class_value[lw.line.asset_class] += lw.value
    for class_id, amount in ideal_by_class.items():  # 6
        line = budget.line(class_id)
        if line is None or line.max_pct is None:
            raise broken(6, f"classe {class_id} sem máximo no orçamento")
        if class_value[class_id] + amount > line.max_pct / 100 * total + _EPS:
            raise broken(6, f"classe {class_id} projetada acima do máximo")
    if proposal.unallocated < -_EPS or (  # 7
        abs(proposal.unallocated - (proposal.budget - proposal.sum_value)) > _EPS
    ):
        raise broken(7, f"saldo_nao_alocado {proposal.unallocated} não fecha")
    if (
        proposal.automatic_action != AUTOMATIC_ACTION
        or contract.automatic_action != AUTOMATIC_ACTION
    ):  # 8
        raise broken(8, "automatic_action diferente de 'nenhuma'")
    round_ = proposal.decision_round
    for ln in proposal.lines:  # 9
        if not (
            ln.verdict
            and ln.price > 0
            and ln.decision_date
            and ln.price_snapshot_date
            and math.isfinite(ln.decision_score)
        ):
            raise broken(9, f"{ln.ticker} sem rastreabilidade completa")
    if round_ is None or round_.date is None:
        raise broken(10, "proposta sem rodada")
    for ln in proposal.lines:  # 10
        if ln.decision_date != round_.date:
            raise broken(
                10, f"{ln.ticker}: DEC de {ln.decision_date}, rodada {round_.date}"
            )
    universe = decision_universe(policy)  # 11 -- completude reverificada
    if {ln.id for ln in universe} != set(round_.decisions) or any(
        note.date != round_.date or note.score is None or not math.isfinite(note.score)
        for note in round_.decisions.values()
    ):
        raise broken(11, "rodada incompleta contra a política vigente")


# --- leitura do vault ----------------------------------------------------------------------


def read_decision_notes(vault_path: str | Path) -> tuple[DecisionNote, ...]:
    """Todas as notas ``DEC-*`` de ``03_Decisions`` (cabeçalho ``type: decision``). O score é
    lido por ``ObsidianRepository.read_decision_score``; valor inválido vira ``None`` (a data
    fica incompleta), nunca um número inventado."""
    directory = Path(vault_path) / DECISIONS_DIR
    if not directory.is_dir():
        return ()
    notes: list[DecisionNote] = []
    for path in sorted(directory.glob("DEC-*.md")):
        meta = _frontmatter(path)
        if meta.get("type") != "decision":
            continue
        ticker, date = meta.get("ticker", "").strip().upper(), meta.get("date", "")
        if not ticker or not date:
            continue
        try:
            score = ObsidianRepository.read_decision_score(path)
        except ValueError:
            score = None
        notes.append(
            DecisionNote(ticker, date, meta.get("new_verdict", ""), score, path.name)
        )
    return tuple(notes)


def read_snapshot_provenance(path: str | Path) -> SnapshotProvenance:
    """Os campos de proveniência do cabeçalho do ``Current.md`` (rev. 4.1), sem interpretação:
    a validação é de ``check_snapshot_provenance``. A data de modificação do arquivo e o
    ``processed_at`` nunca são lidos como data (§3, §10)."""
    meta = _frontmatter(Path(path))

    def field_value(key: str) -> str | None:
        raw = meta.get(key)
        if raw is None:
            return None
        return raw.strip().strip("\"'")

    return SnapshotProvenance(
        snapshot_date=field_value("snapshot_date"),
        basis=field_value("snapshot_date_basis"),
        evidence=field_value("snapshot_date_evidence"),
        captured_at=field_value("captured_at"),
    )


def latest_price_snapshot(
    snapshots_dir: str | Path, cycle: str
) -> tuple[_dt.date | None, Path | None]:
    """A pasta ``AAAA-MM-DD`` mais recente do ciclo em ``snapshots_dir``; a data é o nome."""
    base = Path(snapshots_dir)
    best: tuple[_dt.date, Path] | None = None
    if base.is_dir():
        for folder in base.iterdir():
            try:
                date = _dt.date.fromisoformat(folder.name)
            except ValueError:
                continue
            if folder.is_dir() and date.isoformat()[:7] == cycle:
                if best is None or date > best[0]:
                    best = (date, folder)
    return best if best else (None, None)


def read_price(folder: Path, ticker: str) -> float | None:
    """O campo ``price`` de ``<ticker>.json``; ``None`` se não há arquivo ou preço válido."""
    try:
        raw = json.loads((folder / f"{ticker}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    price = raw.get("price") if isinstance(raw, dict) else None
    if isinstance(price, bool) or not isinstance(price, int | float):
        return None
    return float(price) if math.isfinite(price) and price > 0 else None


def load_inputs(
    vault_path: str | Path, snapshots_dir: str | Path, cycle: str
) -> AporteInputs:
    """Lê tudo o que a proposta usa. Arquivo existente e inválido (contrato, política,
    orçamento, Current.md) levanta ``ValueError`` -- nunca vira um padrão silencioso."""
    vault = Path(vault_path)
    current_path = vault / SNAPSHOT_RELATIVE_PATH
    rows = read_snapshot_rows(current_path) if current_path.exists() else ()
    decisions = read_decision_notes(vault)
    price_date, folder = latest_price_snapshot(snapshots_dir, cycle)
    prices: dict[str, float | None] = {}
    if folder is not None:
        for ticker in {n.ticker for n in decisions if n.date[:7] == cycle}:
            prices[ticker] = read_price(folder, ticker)
    return AporteInputs(
        cycle=cycle,
        contract=load_contract(vault),
        policy=load_policy(vault),
        budget=load_budget(vault),
        rows=rows,
        current_provenance=(
            read_snapshot_provenance(current_path)
            if current_path.exists()
            else SnapshotProvenance()
        ),
        decisions=decisions,
        price_snapshot_date=price_date,
        prices=prices,
        current_snapshot_path=str(current_path),
        price_snapshot_path=str(folder) if folder else "",
    )


def report_relative_path(cycle: str) -> Path:
    return REPORT_DIR / f"Aporte_{cycle}.md"
