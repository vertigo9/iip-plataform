"""Contrato da política de pesos-alvo por ativo.

É uma camada de POLÍTICA, separada do motor de aportes e de rebalanceamento: define o que o
usuário quer (alvo, faixa de tolerância, limites mínimo e máximo, por ativo) e registra o estado
da decisão. Nada aqui compra, vende, aporta ou rebalanceia, e o módulo não importa essas
camadas (há teste de importação). Os percentuais são SEMPRE do usuário: ``build_initial_policy``
cria as linhas com todos os campos vazios e o status ``pendente``; nada é inferido do peso
atual.

Decisões do usuário (20/09/2026) registradas no contrato:
  - granularidade por ativo, com alvo + faixa de tolerância + limites mín/máx individuais;
  - base de cálculo A: a soma dos valores das posições do snapshot (CDBs incluídos);
  - os CDBs entram agrupados numa linha de renda fixa bancária (os registros individuais ficam
    como ``members``, para rastreabilidade); LFTB11 e o FMP-FGTS são ativos próprios;
  - ``FMP-FGTS-DAYCOVAL`` é o identificador canônico do fundo e ``AXIA3`` é o apelido legado do
    registro (o fundo, não a ação: a ação AXIA3 nunca esteve na carteira);
  - BTCI11 e PVBI11 estão zerados e ficam em ``retired``, fora do universo ativo;
  - o monitoramento (sinalizar qualquer saída da faixa) fica DESLIGADO até a política ser
    aprovada; a soma dos alvos (100% ou com reserva) segue em aberto (``sum_rule`` nulo).

Regras de consistência (violá-las é ``ValueError`` com o motivo; nunca há fallback silencioso):
  - ``min <= alvo <= max`` e a faixa ``alvo ± tolerância`` cabe dentro de ``[min, max]``;
  - uma linha ``definido`` tem alvo, tolerância, mín, máx e data da decisão;
  - a política ``aprovada`` exige todas as linhas ativas ``definido``, a regra de soma escolhida
    e cumprida; o monitoramento só pode ligar com a política aprovada;
  - a soma dos alvos já definidos nunca passa de 100%.

Estágio da posição (``stage``): ``estabelecida`` (padrão) ou ``em_construcao``. Uma posição em
construção tem alvo, mínimo e máximo FINAIS e uma previsão de conclusão (``completion_date``
e/ou ``completion_condition``); a tolerância continua sendo só a margem de atenção em torno do
alvo, nunca um indicador de progresso. ``read_weight`` lê o peso atual contra a faixa e distingue
"em formação" (abaixo da faixa numa posição em construção: esperado, não é desvio) de um desvio
de verdade; é uma leitura pura, informativa: nada é sinalizado enquanto o monitoramento estiver
desligado, e nada compra, vende, aporta ou rebalanceia.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from iip.portfolio.vault_snapshot import _parse_brl

POLICY_RELATIVE_PATH = Path("02_Portfolio") / "Politica_Pesos_Alvo.json"
SNAPSHOT_RELATIVE_PATH = Path("02_Portfolio") / "Current.md"
POLICY_SCHEMA = "target-weights-1"

LINE_STATUSES = ("pendente", "definido", "revisavel", "inativo")
STAGE_ESTABLISHED, STAGE_BUILDING = "estabelecida", "em_construcao"
STAGES = (STAGE_ESTABLISHED, STAGE_BUILDING)
APPROVAL_STATUSES = ("pendente", "aprovada")
SUM_RULES = (None, "total_100", "reserva")
KINDS = ("asset", "group")
BASE_A = "A"
BASE_A_DESCRIPTION = (
    "soma dos valores de todas as posições do snapshot (renda fixa bancária incluída)"
)
BANK_FIXED_INCOME_ID = "RF-BANCARIA"
BANK_FIXED_INCOME_CLASS = "renda_fixa"
# apelidos legados do registro para o identificador canônico do snapshot
LEGACY_ALIASES = {"FMP-FGTS-DAYCOVAL": ("AXIA3",)}
# posições zeradas (decisão do usuário): fora do universo ativo, guardadas para rastreio
DEFAULT_RETIRED = (
    ("BTCI11", "2026-09-18", "posição zerada (informado pelo usuário em 20/09/2026)"),
    ("PVBI11", "2026-08-14", "posição zerada (informado pelo usuário em 20/09/2026)"),
)
_SUM_TOLERANCE_PP = 0.01

_LINE_KEYS = frozenset(
    {
        "id",
        "name",
        "asset_class",
        "kind",
        "aliases",
        "members",
        "target_pct",
        "tolerance_pp",
        "min_pct",
        "max_pct",
        "status",
        "rationale",
        "decided_on",
        "stage",
        "completion_date",
        "completion_condition",
    }
)
_ROOT_KEYS = frozenset(
    {
        "type",
        "schema",
        "version",
        "origin",
        "approval_status",
        "base",
        "monitoring",
        "sum_rule",
        "execution",
        "lines",
        "retired",
    }
)
_RETIRED_KEYS = frozenset({"id", "closed_on", "note"})


@dataclass(frozen=True)
class PolicyLine:
    id: str
    name: str
    asset_class: str
    kind: str = "asset"
    aliases: tuple[str, ...] = ()
    members: tuple[str, ...] = ()
    target_pct: float | None = None
    tolerance_pp: float | None = None
    min_pct: float | None = None
    max_pct: float | None = None
    status: str = "pendente"
    rationale: str = ""
    decided_on: str | None = None
    # estágio da posição; em_construcao exige a previsão de conclusão (data e/ou condição)
    stage: str = STAGE_ESTABLISHED
    completion_date: str | None = None
    completion_condition: str = ""

    @property
    def numbers(self) -> tuple[float | None, ...]:
        return (self.target_pct, self.tolerance_pp, self.min_pct, self.max_pct)

    @property
    def complete(self) -> bool:
        return all(value is not None for value in self.numbers)

    def identifiers(self) -> tuple[str, ...]:
        """Tudo o que o snapshot pode usar para se referir a esta linha."""
        return (self.id, *self.aliases, *self.members)


@dataclass(frozen=True)
class RetiredPosition:
    id: str
    closed_on: str
    note: str = ""


@dataclass(frozen=True)
class TargetPolicy:
    version: str
    origin: str
    lines: tuple[PolicyLine, ...] = field(default_factory=tuple)
    retired: tuple[RetiredPosition, ...] = field(default_factory=tuple)
    approval_status: str = "pendente"
    base_id: str = BASE_A
    base_description: str = BASE_A_DESCRIPTION
    monitoring_enabled: bool = False
    sum_rule: str | None = None

    @property
    def content_hash(self) -> str:
        """Hash do conteúdo de política (tudo menos a origem). Duas leituras com o mesmo hash
        são a mesma política."""
        canonical = json.dumps(
            _payload(self, with_origin=False, hash_view=True), sort_keys=True
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def line(self, line_id: str) -> PolicyLine | None:
        return next((ln for ln in self.lines if ln.id == line_id), None)

    def resolve(self, identifier: str) -> PolicyLine | None:
        """A linha a que um identificador do snapshot pertence (id, apelido ou membro)."""
        return next((ln for ln in self.lines if identifier in ln.identifiers()), None)


# --- validação -----------------------------------------------------------------------------


def _fail(label: str, reason: str) -> ValueError:
    return ValueError(f"linha {label!r}: {reason}")


def _check_number(
    label: str, field_name: str, value: float | None, high: float
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _fail(label, f"{field_name} precisa ser um número")
    if not math.isfinite(value) or not 0 <= value <= high:
        raise _fail(label, f"{field_name}={value} fora do intervalo 0 a {high:g}")


def _validate_line(line: PolicyLine) -> None:  # noqa: C901 - uma checagem por regra
    if not line.id.strip():
        raise ValueError("linha sem id")
    label = line.id
    if line.kind not in KINDS:
        raise _fail(label, f"kind {line.kind!r} (use {' ou '.join(KINDS)})")
    if line.kind == "group" and not line.members:
        raise _fail(label, "um grupo precisa de members")
    if line.kind == "asset" and line.members:
        raise _fail(label, "members só vale para grupos")
    if line.status not in LINE_STATUSES:
        raise _fail(label, f"status {line.status!r} (use {', '.join(LINE_STATUSES)})")
    for name, value in (
        ("target_pct", line.target_pct),
        ("min_pct", line.min_pct),
        ("max_pct", line.max_pct),
    ):
        _check_number(label, name, value, 100.0)
    _check_number(label, "tolerance_pp", line.tolerance_pp, 100.0)
    if line.decided_on is not None:
        try:
            _dt.date.fromisoformat(line.decided_on)
        except ValueError as exc:
            raise _fail(
                label, f"decided_on {line.decided_on!r} não é AAAA-MM-DD"
            ) from exc
    target, tolerance, low, high = line.numbers
    if low is not None and high is not None and low > high:
        raise _fail(label, f"min_pct ({low:g}) maior que max_pct ({high:g})")
    if target is not None and low is not None and target < low:
        raise _fail(label, f"alvo ({target:g}) abaixo do mínimo ({low:g})")
    if target is not None and high is not None and target > high:
        raise _fail(label, f"alvo ({target:g}) acima do máximo ({high:g})")
    if target is not None and tolerance is not None:
        if low is not None and target - tolerance < low:
            raise _fail(
                label,
                f"a faixa (alvo - tolerância = {target - tolerance:g}) fica abaixo do "
                f"mínimo ({low:g})",
            )
        if high is not None and target + tolerance > high:
            raise _fail(
                label,
                f"a faixa (alvo + tolerância = {target + tolerance:g}) passa do máximo "
                f"({high:g})",
            )
    if line.stage not in STAGES:
        raise _fail(label, f"stage {line.stage!r} (use {' ou '.join(STAGES)})")
    if line.completion_date is not None:
        try:
            _dt.date.fromisoformat(line.completion_date)
        except ValueError as exc:
            raise _fail(
                label, f"completion_date {line.completion_date!r} não é AAAA-MM-DD"
            ) from exc
    has_completion = bool(line.completion_date) or bool(
        line.completion_condition.strip()
    )
    if line.stage == STAGE_ESTABLISHED and has_completion:
        raise _fail(
            label,
            "completion_date/completion_condition só valem para posição em_construcao",
        )
    if line.stage == STAGE_BUILDING and line.status != "inativo":
        if not has_completion:
            raise _fail(
                label,
                "em_construcao exige a previsão de conclusão "
                "(completion_date ou completion_condition)",
            )
        if (
            line.completion_date
            and line.decided_on
            and line.completion_date < line.decided_on
        ):
            raise _fail(
                label,
                f"completion_date ({line.completion_date}) anterior à data da decisão "
                f"({line.decided_on})",
            )
    if line.status == "definido":
        if not line.complete:
            raise _fail(label, "definido exige alvo, tolerância, mínimo e máximo")
        if not line.decided_on:
            raise _fail(label, "definido exige a data da decisão (decided_on)")


def validate(policy: TargetPolicy) -> None:
    """Levanta ``ValueError`` com o motivo se a política não serve."""
    if not policy.version.strip():
        raise ValueError("a política precisa de uma versão")
    if policy.base_id != BASE_A:
        raise ValueError(
            f"base {policy.base_id!r} desconhecida (hoje só existe a base A)"
        )
    if policy.approval_status not in APPROVAL_STATUSES:
        raise ValueError(
            f"approval_status {policy.approval_status!r} (use {' ou '.join(APPROVAL_STATUSES)})"
        )
    if policy.sum_rule not in SUM_RULES:
        raise ValueError(
            f"sum_rule {policy.sum_rule!r} (use nulo, total_100 ou reserva)"
        )
    if not policy.lines:
        raise ValueError("a política não tem linhas")
    seen: dict[str, str] = {}
    for line in policy.lines:
        _validate_line(line)
        for identifier in line.identifiers():
            if identifier in seen:
                raise _fail(
                    line.id,
                    f"o identificador {identifier!r} já pertence à linha {seen[identifier]!r}",
                )
            seen[identifier] = line.id
    for retired in policy.retired:
        if retired.id in seen:
            raise ValueError(
                f"{retired.id!r} está em retired e também na linha {seen[retired.id]!r}"
            )
        try:
            _dt.date.fromisoformat(retired.closed_on)
        except ValueError as exc:
            raise ValueError(f"retired {retired.id!r}: closed_on inválido") from exc

    active = [ln for ln in policy.lines if ln.status != "inativo"]
    total = sum(ln.target_pct for ln in active if ln.target_pct is not None)
    if total > 100 + _SUM_TOLERANCE_PP:
        raise ValueError(f"a soma dos alvos definidos ({total:g}%) passa de 100%")
    if policy.monitoring_enabled and policy.approval_status != "aprovada":
        raise ValueError("o monitoramento só pode ligar com a política aprovada")
    if policy.approval_status == "aprovada":
        pending = [ln.id for ln in active if ln.status != "definido"]
        if pending:
            raise ValueError(f"política aprovada com linhas não definidas: {pending}")
        if policy.sum_rule is None:
            raise ValueError(
                "política aprovada exige a regra de soma dos alvos (sum_rule)"
            )
        if policy.sum_rule == "total_100" and abs(total - 100) > _SUM_TOLERANCE_PP:
            raise ValueError(f"total_100: os alvos somam {total:g}%, não 100%")


# --- serialização --------------------------------------------------------------------------


def _line_payload(line: PolicyLine, *, hash_view: bool = False) -> dict:
    payload = {
        "id": line.id,
        "name": line.name,
        "asset_class": line.asset_class,
        "kind": line.kind,
        "aliases": list(line.aliases),
        "members": list(line.members),
        "target_pct": line.target_pct,
        "tolerance_pp": line.tolerance_pp,
        "min_pct": line.min_pct,
        "max_pct": line.max_pct,
        "status": line.status,
        "rationale": line.rationale,
        "decided_on": line.decided_on,
    }
    extra = {
        "stage": line.stage,
        "completion_date": line.completion_date,
        "completion_condition": line.completion_condition,
    }
    # o arquivo mostra sempre os campos de estágio; o hash só os vê quando fogem do padrão,
    # para uma política sem posição em construção manter o mesmo hash de antes do estágio
    default = (
        line.stage == STAGE_ESTABLISHED
        and not line.completion_date
        and not line.completion_condition
    )
    if not (hash_view and default):
        payload.update(extra)
    return payload


def _payload(
    policy: TargetPolicy, *, with_origin: bool = True, hash_view: bool = False
) -> dict:
    payload = {
        "type": "target_weight_policy",
        "schema": POLICY_SCHEMA,
        "version": policy.version,
        "approval_status": policy.approval_status,
        "base": {"id": policy.base_id, "description": policy.base_description},
        "monitoring": {
            "enabled": policy.monitoring_enabled,
            "rule": "sinalizar qualquer saída da faixa",
        },
        "sum_rule": policy.sum_rule,
        "execution": "nenhum aporte, venda ou rebalanceamento é executado por esta política",
        "lines": [_line_payload(ln, hash_view=hash_view) for ln in policy.lines],
        "retired": [
            {"id": r.id, "closed_on": r.closed_on, "note": r.note}
            for r in policy.retired
        ],
    }
    if with_origin:
        payload["origin"] = policy.origin
    return payload


def save_policy(vault_path: str | Path, policy: TargetPolicy) -> Path:
    validate(policy)
    path = Path(vault_path) / POLICY_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_payload(policy), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def _parse_line(item: object) -> PolicyLine:
    if not isinstance(item, dict):
        raise ValueError(f"linha mal formada (não é um objeto): {item!r}")
    label = str(item.get("id", "?"))
    unknown = set(item) - _LINE_KEYS
    if unknown:
        raise _fail(label, f"chave desconhecida {sorted(unknown)}")
    missing = [k for k in ("id", "name", "asset_class") if k not in item]
    if missing:
        raise _fail(label, f"faltam as chaves {missing}")
    try:
        return PolicyLine(
            id=str(item["id"]),
            name=str(item["name"]),
            asset_class=str(item["asset_class"]),
            kind=str(item.get("kind", "asset")),
            aliases=tuple(str(a) for a in item.get("aliases", ())),
            members=tuple(str(m) for m in item.get("members", ())),
            target_pct=item.get("target_pct"),
            tolerance_pp=item.get("tolerance_pp"),
            min_pct=item.get("min_pct"),
            max_pct=item.get("max_pct"),
            status=str(item.get("status", "pendente")),
            rationale=str(item.get("rationale", "")),
            decided_on=item.get("decided_on"),
            stage=str(item.get("stage", STAGE_ESTABLISHED)),
            completion_date=item.get("completion_date"),
            completion_condition=str(item.get("completion_condition", "")),
        )
    except TypeError as exc:
        raise _fail(label, f"valor mal formado ({exc})") from exc


def load_policy(vault_path: str | Path) -> TargetPolicy | None:
    """A política gravada, ou ``None`` se não há arquivo. Um arquivo que existe mas está errado
    levanta ``ValueError`` com o motivo: nunca cai em silêncio para um padrão."""
    path = Path(vault_path) / POLICY_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: não é um JSON válido ({exc})") from exc
    try:
        if not isinstance(raw, dict):
            raise ValueError("a raiz precisa ser um objeto")
        unknown = set(raw) - _ROOT_KEYS
        if unknown:
            raise ValueError(f"chave desconhecida na raiz {sorted(unknown)}")
        if raw.get("schema") != POLICY_SCHEMA:
            raise ValueError(
                f"schema {raw.get('schema')!r}, esperado {POLICY_SCHEMA!r}"
            )
        base = raw.get("base", {})
        monitoring = raw.get("monitoring", {})
        retired = []
        for item in raw.get("retired", ()):
            if not isinstance(item, dict) or set(item) - _RETIRED_KEYS:
                raise ValueError(f"retired mal formado: {item!r}")
            retired.append(
                RetiredPosition(
                    str(item["id"]), str(item["closed_on"]), str(item.get("note", ""))
                )
            )
        policy = TargetPolicy(
            version=str(raw["version"]),
            origin=str(raw.get("origin", "")),
            lines=tuple(_parse_line(item) for item in raw["lines"]),
            retired=tuple(retired),
            approval_status=str(raw.get("approval_status", "pendente")),
            base_id=str(base.get("id", BASE_A)),
            base_description=str(base.get("description", BASE_A_DESCRIPTION)),
            monitoring_enabled=monitoring.get("enabled", False),
            sum_rule=raw.get("sum_rule"),
        )
        if not isinstance(policy.monitoring_enabled, bool):
            raise ValueError("monitoring.enabled precisa ser true ou false")
        validate(policy)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{path}: política mal formada ({exc!r})") from exc
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return policy


# --- o snapshot e a montagem inicial -------------------------------------------------------


@dataclass(frozen=True)
class SnapshotRow:
    id: str
    name: str
    asset_class: str
    value: float


def read_snapshot_rows(path: str | Path) -> tuple[SnapshotRow, ...]:
    """As linhas ativas de ``Current.md`` com o identificador do próprio snapshot (sem o apelido
    do registro), a classe original e o valor."""
    file_path = Path(path)
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ValueError(f"{file_path}: arquivo do snapshot não encontrado") from exc
    header = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("| ID ")), None
    )
    if header is None:
        raise ValueError(
            f"{file_path}: cabeçalho de tabela '| ID | ...' não encontrado"
        )
    rows: list[SnapshotRow] = []
    for line in lines[header + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 10:
            raise ValueError(
                f"{file_path}: linha com colunas a menos: {stripped[:60]!r}"
            )
        if cells[9].casefold() != "active":
            continue
        value = _parse_brl(cells[6])
        if value is None:
            raise ValueError(f"{file_path}: {cells[0]} sem valor")
        rows.append(SnapshotRow(cells[0], cells[1], cells[2], value))
    if not rows:
        raise ValueError(f"{file_path}: nenhuma posição ativa")
    return tuple(rows)


def build_initial_policy(
    rows: tuple[SnapshotRow, ...],
    *,
    version: str,
    origin: str = "montada a partir do snapshot; todos os pesos, tolerâncias e limites vazios",
) -> TargetPolicy:
    """As linhas da política a partir do snapshot: um ativo por linha, os CDBs (renda fixa
    bancária) agrupados numa só. NENHUM percentual é preenchido."""
    lines: list[PolicyLine] = []
    bank_members: list[str] = []
    for row in rows:
        if row.asset_class == BANK_FIXED_INCOME_CLASS:
            bank_members.append(row.id)
            continue
        lines.append(
            PolicyLine(
                id=row.id,
                name=row.name,
                asset_class=row.asset_class,
                aliases=LEGACY_ALIASES.get(row.id, ()),
            )
        )
    if bank_members:
        lines.append(
            PolicyLine(
                id=BANK_FIXED_INCOME_ID,
                name="Renda fixa bancária (CDBs)",
                asset_class=BANK_FIXED_INCOME_CLASS,
                kind="group",
                members=tuple(bank_members),
            )
        )
    retired = tuple(RetiredPosition(*item) for item in DEFAULT_RETIRED)
    policy = TargetPolicy(
        version=version, origin=origin, lines=tuple(lines), retired=retired
    )
    validate(policy)
    return policy


# --- reconciliação e pesos atuais (só leitura) ---------------------------------------------


@dataclass(frozen=True)
class LineWeight:
    line: PolicyLine
    value: float
    weight_pct: float  # base A: valor da linha sobre a soma das posições
    present: tuple[str, ...]  # os identificadores do snapshot que compõem a linha


@dataclass(frozen=True)
class Reconciliation:
    total: float
    weights: tuple[LineWeight, ...]
    uncovered: tuple[SnapshotRow, ...]  # no snapshot e em nenhuma linha
    absent_lines: tuple[PolicyLine, ...]  # linhas ativas sem posição no snapshot
    reopened: tuple[SnapshotRow, ...]  # posições que a política tem como zeradas
    missing_members: tuple[tuple[str, str], ...]  # (linha, membro) que saiu do snapshot
    new_members: tuple[
        tuple[str, SnapshotRow], ...
    ]  # (linha, posição) de classe do grupo

    @property
    def consistent(self) -> bool:
        return not (
            self.uncovered or self.absent_lines or self.reopened or self.new_members
        )


def reconcile(policy: TargetPolicy, rows: tuple[SnapshotRow, ...]) -> Reconciliation:
    """Confere a política contra o snapshot e calcula o peso atual de cada linha na base A."""
    total = sum(r.value for r in rows)
    retired_ids = {r.id for r in policy.retired}
    by_line: dict[str, list[SnapshotRow]] = {ln.id: [] for ln in policy.lines}
    uncovered: list[SnapshotRow] = []
    reopened: list[SnapshotRow] = []
    new_members: list[tuple[str, SnapshotRow]] = []
    groups_by_class = {ln.asset_class: ln for ln in policy.lines if ln.kind == "group"}
    for row in rows:
        line = policy.resolve(row.id)
        if line is not None:
            by_line[line.id].append(row)
        elif row.id in retired_ids:
            reopened.append(row)
        elif row.asset_class in groups_by_class:
            group = groups_by_class[row.asset_class]
            by_line[group.id].append(row)
            new_members.append((group.id, row))
        else:
            uncovered.append(row)
    weights = []
    absent = []
    missing_members = []
    for line in policy.lines:
        present = by_line[line.id]
        value = sum(r.value for r in present)
        weights.append(
            LineWeight(
                line,
                value,
                value / total * 100 if total else 0.0,
                tuple(r.id for r in present),
            )
        )
        if not present and line.status != "inativo":
            absent.append(line)
        if line.kind == "group":
            here = {r.id for r in present}
            missing_members.extend((line.id, m) for m in line.members if m not in here)
    return Reconciliation(
        total,
        tuple(weights),
        tuple(uncovered),
        tuple(absent),
        tuple(reopened),
        tuple(missing_members),
        tuple(new_members),
    )


# --- leitura do peso atual contra a faixa (pura, informativa) ------------------------------

_READ_EPSILON = 1e-9
DEVIATION_STATES = frozenset({"fora_da_faixa", "abaixo_do_minimo", "acima_do_maximo"})


@dataclass(frozen=True)
class WeightReading:
    """Como o peso atual de uma linha se compara com a faixa dela. ``is_deviation`` é o que um
    monitor futuro sinalizaria; "em formação" NÃO é desvio."""

    state: str  # sem_faixa, inativa, na_faixa, em_formacao ou um de DEVIATION_STATES
    label: str

    @property
    def is_deviation(self) -> bool:
        return self.state in DEVIATION_STATES


def read_weight(line: PolicyLine, weight_pct: float) -> WeightReading:
    """Lê ``weight_pct`` (peso atual na base A, em %) contra ``alvo ± tolerância`` e os limites.

    Posição ``estabelecida``: abaixo do mínimo ou acima do máximo são desvios; fora da faixa mas
    dentro dos limites também. Posição ``em_construcao``: estar ABAIXO da faixa é esperado
    ("em formação", com o aviso de estar abaixo do mínimo final quando for o caso); passar da
    faixa ou do máximo continua sendo desvio. Sem os quatro números, não há faixa para ler.
    Nada aqui sinaliza, decide ou executa: é só a leitura."""
    if line.status == "inativo":
        return WeightReading("inativa", "linha inativa")
    if not line.complete:
        return WeightReading("sem_faixa", "sem faixa definida")
    target, tolerance, low, high = line.numbers
    lower_edge, upper_edge = target - tolerance, target + tolerance
    if weight_pct > high + _READ_EPSILON:
        return WeightReading("acima_do_maximo", "acima do máximo")
    if weight_pct > upper_edge + _READ_EPSILON:
        return WeightReading("fora_da_faixa", "fora da faixa (acima do alvo)")
    if weight_pct < lower_edge - _READ_EPSILON:
        below_min = weight_pct < low - _READ_EPSILON
        if line.stage == STAGE_BUILDING:
            reason = "abaixo do mínimo final" if below_min else "abaixo da faixa"
            return WeightReading("em_formacao", f"em formação: {reason}")
        if below_min:
            return WeightReading("abaixo_do_minimo", "abaixo do mínimo")
        return WeightReading("fora_da_faixa", "fora da faixa (abaixo do alvo)")
    return WeightReading("na_faixa", "dentro da faixa")
