"""Contrato do orçamento por classe: alvo + faixa de tolerância + limites mín/máx por CLASSE
(camada agregada), separado e independente da política de pesos-alvo POR ATIVO
(``target_policy.py``).

É uma camada de POLÍTICA, igual à individual: não compra, vende, aporta nem rebalanceia, e o
módulo não importa essas camadas (há teste de importação, espelhando o de ``target_policy``).
``automatic_action`` em qualquer leitura de desvio é sempre ``"nenhuma"`` -- travado, como em
``monitoring_event.py``: bloquear a gravação de uma configuração inválida (ver abaixo) não é
uma decisão de investimento, é validação de dado.

Decisões do usuário (24/09/2026) registradas neste contrato:
  - as classes são as mesmas 7 de ``layers.py`` (``CLASS_LABELS``): não existe uma segunda
    taxonomia. ``asset_class`` de cada ``PolicyLine`` já é o identificador da classe;
  - a soma dos alvos das 7 classes definidas NUNCA passa de 100% (mesma tolerância de
    ``target_policy``), mas os 7 orçamentos NÃO precisam somar 100%: a soma é um TETO, nunca
    uma meta a ser atingida. Isso fica documentado aqui e não deve ser presumido em outro lugar;
  - ``ClassBudget.approval_status`` é próprio, independente do ``approval_status`` da política
    individual -- dá para ter os dois ``pendente`` ao mesmo tempo, sem nenhuma restrição ativa;
  - fora da FAIXA DE TOLERÂNCIA da classe (alvo ± tolerância) é sempre só informativo, aprovado
    ou não -- nunca bloqueia nada;
  - fora do MÍNIMO/MÁXIMO (rígido) da classe É uma restrição estrutural, mas só entra em vigor
    quando ``approval_status == "aprovada"``: nesse caso, uma tentativa de gravar uma NOVA
    versão da política individual cuja soma de alvos definidos por classe estoure o mín/máx de
    uma linha ``definida`` do orçamento é recusada (``ValueError``) e NADA é gravado -- nem a
    política individual, nem o orçamento. Com o orçamento ``pendente`` (o estado de hoje), o
    mesmo desvio é só relatado, nunca bloqueia.

Ordem de gravação garantida por ``save_policy_guarded`` (o único caminho que deve gravar uma
NOVA versão da política individual quando existe orçamento por classe):

    política candidata (em memória, nada gravado ainda)
        -> target_policy.validate(candidata)          [já existe; ValueError para aqui]
        -> class_budget.enforce(orcamento, candidata)  [ValueError se classe aprovada estourar]
        -> save_policy(vault, candidata)               [só roda se as duas passarem]

Como ``TargetPolicy`` é imutável e representa o conjunto INTEIRO de linhas (não um diff), a
"política candidata" já É a nova composição da classe -- não há necessidade de somar
separadamente "soma atual + efeito da mudança": ``class_sums(candidata)`` já reflete o estado
depois da mudança proposta, antes de qualquer escrita em disco.

Três dimensões diferentes, que este módulo NUNCA confunde entre si (achado da auditoria de
consistência de 24/09/2026, ao preencher os 7 targets de classe reais):
  - **peso real** (``Current.md`` via ``reconcile()``): o estado observado da carteira;
  - **alvo individual** (``PolicyLine.target_pct``): a referência/intenção declarada de UM
    ativo -- sob a regra ``referencias_individuais`` (a de hoje), 14 ações com alvo 5% cada
    somam 70%, e isso não significa "70% de intenção para a classe Ações": são 14 referências
    independentes, cada uma válida por si só, sem se somar a um sentido de carteira;
  - **alvo de classe** (``ClassBudgetLine.target_pct``, este módulo): a intenção AGREGADA e
    deliberada para a classe inteira, decidida separadamente pelo usuário.

``class_sums(policy)`` é uma operação matemática válida sobre os ``target_pct`` individuais,
mas o resultado só tem SIGNIFICADO de alocação de classe quando a própria política declara
isso via ``TargetPolicy.sum_rule`` (``"total_100"`` ou ``"reserva"``: aí os alvos individuais
representam de fato frações de uma carteira real). Sob ``sum_rule`` nulo ou
``"referencias_individuais"`` -- o caso de hoje, nas 35 linhas -- a soma é só um número
mecânico sem esse significado, e ``prospective_class_targets`` retorna ``{}`` para deixar isso
explícito: **não fabricar um alvo de classe a partir de referências que nunca pretenderam
somar**.

Duas camadas usam a MESMA função de comparação (``check_against_targets``), alimentada por
fontes diferentes conforme o propósito -- ela é agnóstica à origem do dado, só responde "dado
este mapa de valores por classe, quais classes estão fora da tolerância ou dos limites?":

  - **Camada A -- monitoramento** (leitura, NUNCA bloqueia): ``real_class_weights(rows)``, o
    peso real via ``reconcile()``/``Current.md`` -- "onde a carteira está frente ao
    orçamento?";
  - **Camada B -- guard de escrita** (``enforce``, usado por ``save_policy_guarded``, só
    bloqueia com o orçamento ``aprovada``): ``prospective_class_targets(policy)`` -- só produz
    um sinal quando ``sum_rule`` autoriza a soma dos alvos individuais como alocação real;
    caso contrário, o dicionário vem vazio e ``enforce`` não bloqueia nada por essa via (um
    dicionário vazio para uma classe significa "esta dimensão não é declarada pela política",
    nunca "o alvo é zero").
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from iip.portfolio.layers import CLASS_LABELS
from iip.portfolio.policy_validation import check_number, check_target_range, fail
from iip.portfolio.target_policy import SnapshotRow, TargetPolicy, save_policy
from iip.portfolio.target_policy import validate as validate_policy

# sum_rule sob os quais os target_pct individuais representam de fato frações de uma carteira
# real (e portanto podem alimentar um sinal prospectivo de classe); ver docstring do módulo.
_AGGREGATING_SUM_RULES = frozenset({"total_100", "reserva"})

BUDGET_RELATIVE_PATH = Path("02_Portfolio") / "Orcamento_Classe.json"
BUDGET_SCHEMA = "class-budget-1"
CLASS_IDS = tuple(CLASS_LABELS)  # a mesma taxonomia de layers.py, nenhuma outra

LINE_STATUSES = ("pendente", "definido")
APPROVAL_STATUSES = ("pendente", "aprovada")
BREACH_TOLERANCE = "tolerancia"  # informativo, nunca bloqueia
BREACH_MIN_MAX = "min_max"  # restrição estrutural; bloqueia só com orçamento aprovado
AUTOMATIC_ACTION = "nenhuma"  # campo travado: nunca decide nem executa

_SUM_TOLERANCE_PP = 0.01

_LINE_KEYS = frozenset(
    {
        "class_id",
        "target_pct",
        "tolerance_pp",
        "min_pct",
        "max_pct",
        "status",
        "rationale",
        "decided_on",
    }
)
_ROOT_KEYS = frozenset(
    {"type", "schema", "version", "origin", "approval_status", "lines"}
)


@dataclass(frozen=True)
class ClassBudgetLine:
    class_id: str
    target_pct: float | None = None
    tolerance_pp: float | None = None
    min_pct: float | None = None
    max_pct: float | None = None
    status: str = "pendente"
    rationale: str = ""
    decided_on: str | None = None

    @property
    def numbers(self) -> tuple[float | None, ...]:
        return (self.target_pct, self.tolerance_pp, self.min_pct, self.max_pct)

    @property
    def complete(self) -> bool:
        return all(value is not None for value in self.numbers)


@dataclass(frozen=True)
class ClassBudget:
    version: str
    origin: str
    lines: tuple[ClassBudgetLine, ...] = field(default_factory=tuple)
    approval_status: str = "pendente"

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(_payload(self, with_origin=False), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def line(self, class_id: str) -> ClassBudgetLine | None:
        return next((ln for ln in self.lines if ln.class_id == class_id), None)


@dataclass(frozen=True)
class ClassBreach:
    """Leitura pura: um valor de classe (peso real ou alvo prospectivo, conforme a fonte
    passada a ``check_against_targets``) contra a faixa do orçamento. Sempre computada
    (informativa); nunca decide, executa, aporta ou rebalanceia.
    """

    class_id: str
    kind: str  # BREACH_TOLERANCE ou BREACH_MIN_MAX
    sum_pct: float  # o valor comparado: peso real OU alvo prospectivo, conforme a fonte
    target_pct: float
    tolerance_pp: float
    min_pct: float
    max_pct: float
    automatic_action: str = AUTOMATIC_ACTION


# --- validação -----------------------------------------------------------------------------


def _validate_line(line: ClassBudgetLine) -> None:
    if line.class_id not in CLASS_IDS:
        raise fail(
            line.class_id, f"classe desconhecida (use uma de {', '.join(CLASS_IDS)})"
        )
    label = line.class_id
    if line.status not in LINE_STATUSES:
        raise fail(label, f"status {line.status!r} (use {', '.join(LINE_STATUSES)})")
    for name, value in (
        ("target_pct", line.target_pct),
        ("min_pct", line.min_pct),
        ("max_pct", line.max_pct),
    ):
        check_number(label, name, value, 100.0)
    check_number(label, "tolerance_pp", line.tolerance_pp, 100.0)
    target, tolerance, low, high = line.numbers
    check_target_range(label, target, tolerance, low, high)
    if line.decided_on is not None:
        try:
            _dt.date.fromisoformat(line.decided_on)
        except ValueError as exc:
            raise fail(
                label, f"decided_on {line.decided_on!r} não é AAAA-MM-DD"
            ) from exc
    if line.status == "definido":
        if not line.complete:
            raise fail(label, "definido exige alvo, tolerância, mínimo e máximo")
        if not line.decided_on:
            raise fail(label, "definido exige a data da decisão (decided_on)")


def budget_target_sum(budget: ClassBudget) -> float:
    """A soma dos alvos definidos das 7 classes -- um TETO informativo, nunca uma meta: os
    orçamentos de classe não precisam somar 100% da carteira."""
    return sum(ln.target_pct for ln in budget.lines if ln.target_pct is not None)


def validate(budget: ClassBudget) -> None:
    """Levanta ``ValueError`` com o motivo se o orçamento não serve."""
    if not budget.version.strip():
        raise ValueError("o orçamento precisa de uma versão")
    if budget.approval_status not in APPROVAL_STATUSES:
        raise ValueError(
            f"approval_status {budget.approval_status!r} "
            f"(use {' ou '.join(APPROVAL_STATUSES)})"
        )
    if not budget.lines:
        raise ValueError("o orçamento não tem linhas")
    seen: set[str] = set()
    for line in budget.lines:
        _validate_line(line)
        if line.class_id in seen:
            raise fail(line.class_id, "classe repetida no orçamento")
        seen.add(line.class_id)
    missing = set(CLASS_IDS) - seen
    if missing:
        raise ValueError(f"faltam classes no orçamento: {sorted(missing)}")
    total = budget_target_sum(budget)
    if total > 100 + _SUM_TOLERANCE_PP:
        raise ValueError(
            f"a soma dos alvos de classe definidos ({total:g}%) passa de 100% (teto, não meta)"
        )
    if budget.approval_status == "aprovada":
        pending = [ln.class_id for ln in budget.lines if ln.status != "definido"]
        if pending:
            raise ValueError(f"orçamento aprovado com classes não definidas: {pending}")


# --- serialização --------------------------------------------------------------------------


def _line_payload(line: ClassBudgetLine) -> dict:
    return {
        "class_id": line.class_id,
        "target_pct": line.target_pct,
        "tolerance_pp": line.tolerance_pp,
        "min_pct": line.min_pct,
        "max_pct": line.max_pct,
        "status": line.status,
        "rationale": line.rationale,
        "decided_on": line.decided_on,
    }


def _payload(budget: ClassBudget, *, with_origin: bool = True) -> dict:
    payload = {
        "type": "class_budget_policy",
        "schema": BUDGET_SCHEMA,
        "version": budget.version,
        "approval_status": budget.approval_status,
        "lines": [_line_payload(ln) for ln in budget.lines],
    }
    if with_origin:
        payload["origin"] = budget.origin
    return payload


def save_budget(vault_path: str | Path, budget: ClassBudget) -> Path:
    validate(budget)
    path = Path(vault_path) / BUDGET_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_payload(budget), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def _parse_line(item: object) -> ClassBudgetLine:
    if not isinstance(item, dict):
        raise ValueError(f"linha mal formada (não é um objeto): {item!r}")
    label = str(item.get("class_id", "?"))
    unknown = set(item) - _LINE_KEYS
    if unknown:
        raise fail(label, f"chave desconhecida {sorted(unknown)}")
    if "class_id" not in item:
        raise fail(label, "falta a chave class_id")
    try:
        return ClassBudgetLine(
            class_id=str(item["class_id"]),
            target_pct=item.get("target_pct"),
            tolerance_pp=item.get("tolerance_pp"),
            min_pct=item.get("min_pct"),
            max_pct=item.get("max_pct"),
            status=str(item.get("status", "pendente")),
            rationale=str(item.get("rationale", "")),
            decided_on=item.get("decided_on"),
        )
    except TypeError as exc:
        raise fail(label, f"valor mal formado ({exc})") from exc


def load_budget(vault_path: str | Path) -> ClassBudget | None:
    """O orçamento gravado, ou ``None`` se não há arquivo. Um arquivo que existe mas está errado
    levanta ``ValueError`` com o motivo: nunca cai em silêncio para um padrão."""
    path = Path(vault_path) / BUDGET_RELATIVE_PATH
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
        if raw.get("schema") != BUDGET_SCHEMA:
            raise ValueError(
                f"schema {raw.get('schema')!r}, esperado {BUDGET_SCHEMA!r}"
            )
        budget = ClassBudget(
            version=str(raw["version"]),
            origin=str(raw.get("origin", "")),
            lines=tuple(_parse_line(item) for item in raw["lines"]),
            approval_status=str(raw.get("approval_status", "pendente")),
        )
        validate(budget)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{path}: orçamento mal formado ({exc!r})") from exc
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return budget


def build_initial_budget(
    *, version: str, origin: str = "criado com todas as 7 classes vazias"
) -> ClassBudget:
    """As 7 linhas de classe, todas ``pendente`` e com os campos vazios. NENHUM percentual é
    preenchido por esta função -- os valores são sempre do usuário."""
    lines = tuple(ClassBudgetLine(class_id=class_id) for class_id in CLASS_IDS)
    budget = ClassBudget(version=version, origin=origin, lines=lines)
    validate(budget)
    return budget


# --- leitura contra a política individual (só leitura, nunca decide) -----------------------


def class_sums(policy: TargetPolicy) -> dict[str, float]:
    """A soma, por classe, dos ``target_pct`` DEFINIDOS das linhas ativas da política
    individual -- a mesma composição que ``layers.py`` já soma por classe (``class_targets``),
    só que aqui como um dicionário simples, sem depender do snapshot.

    É uma operação matemática válida, mas o resultado só tem significado de alocação de classe
    quando ``TargetPolicy.sum_rule`` autoriza isso -- ver ``prospective_class_targets``. Usar
    esta função diretamente como guard de orçamento reproduz o bug que a auditoria de
    24/09/2026 encontrou (14 ações x 5% interpretadas como 70% de intenção da classe Ações).
    """
    sums: dict[str, float] = defaultdict(float)
    for line in policy.lines:
        if line.status == "inativo" or line.target_pct is None:
            continue
        sums[line.asset_class] += line.target_pct
    return dict(sums)


def prospective_class_targets(policy: TargetPolicy) -> dict[str, float]:
    """O agregado de classe a usar pelo GUARD de escrita (``enforce``/``save_policy_guarded``).

    Só existe quando a própria política declara, via ``sum_rule``, que os alvos individuais
    representam alocação real da carteira (``"total_100"`` ou ``"reserva"``). Sob
    ``"referencias_individuais"`` ou ``sum_rule`` nulo -- o caso de hoje, nas 35 linhas --
    retorna ``{}``: não porque as classes tenham alvo 0%, mas porque essa dimensão não é
    declarada pela política. ``check_against_targets`` trata uma classe ausente do dicionário
    como "sem dado", nunca como "dado zero"."""
    if policy.sum_rule not in _AGGREGATING_SUM_RULES:
        return {}
    return class_sums(policy)


def real_class_weights(rows: tuple[SnapshotRow, ...]) -> dict[str, float]:
    """O peso REAL por classe (``Current.md``), para a camada A -- monitoramento informativo,
    nunca bloqueia. Mesma agregação que ``layers.py`` já faz por classe, aqui como um
    dicionário simples, sem depender do registro/setor/segmento (que ``layers.py`` usa para as
    camadas mais profundas e este módulo não precisa)."""
    total = sum(r.value for r in rows)
    if total <= 0:
        return {}
    sums: dict[str, float] = defaultdict(float)
    for row in rows:
        sums[row.asset_class] += row.value
    return {class_id: value / total * 100 for class_id, value in sums.items()}


def check_against_targets(
    budget: ClassBudget, class_values: dict[str, float]
) -> tuple[ClassBreach, ...]:
    """Leitura pura, agnóstica à origem do dado: dado este mapa de valores por classe (peso
    real, via ``real_class_weights``, ou alvo prospectivo, via ``prospective_class_targets``),
    quais classes ``definidas`` do orçamento estão fora da tolerância ou dos limites? Uma
    classe ausente de ``class_values`` é ignorada (sem dado, não é tratada como zero). Não
    decide, executa, aporta ou rebalanceia -- só quem chama (``enforce``) decide se um
    ``BREACH_MIN_MAX`` bloqueia alguma coisa."""
    breaches: list[ClassBreach] = []
    for line in budget.lines:
        if line.status != "definido" or line.class_id not in class_values:
            continue
        current = class_values[line.class_id]
        target, tolerance, low, high = line.numbers
        if current < low or current > high:
            kind = BREACH_MIN_MAX
        elif current < target - tolerance or current > target + tolerance:
            kind = BREACH_TOLERANCE
        else:
            continue
        breaches.append(
            ClassBreach(line.class_id, kind, current, target, tolerance, low, high)
        )
    return tuple(breaches)


def enforce(budget: ClassBudget | None, policy: TargetPolicy) -> None:
    """Levanta ``ValueError`` -- e não grava nada -- quando o orçamento está ``aprovada`` e a
    política candidata tem um alvo de classe PROSPECTIVO (``prospective_class_targets``, só
    existe sob ``sum_rule`` "total_100"/"reserva") que estoura o mín/máx (rígido) de alguma
    classe ``definida``. Sob ``referencias_individuais`` (o caso de hoje) o dicionário vem
    vazio e isto nunca bloqueia nada -- uma edição isolada de uma linha não é rejeitada pela
    soma mecânica de placeholders de outras linhas. Com o orçamento ``None`` ou ``pendente``,
    também nunca bloqueia (a leitura de desvio segue disponível via ``check_against_targets``,
    só informativa)."""
    if budget is None or budget.approval_status != "aprovada":
        return
    for breach in check_against_targets(budget, prospective_class_targets(policy)):
        if breach.kind != BREACH_MIN_MAX:
            continue
        raise ValueError(
            f"classe {breach.class_id!r}: alvo agregado prospectivo "
            f"({breach.sum_pct:g}%) fora do orçamento aprovado "
            f"[{breach.min_pct:g}%, {breach.max_pct:g}%]"
        )


def save_policy_guarded(
    vault_path: str | Path, candidate_policy: TargetPolicy, budget: ClassBudget | None
) -> Path:
    """O único caminho que deve gravar uma NOVA versão da política individual quando existe
    orçamento por classe: valida a política, depois o orçamento (nessa ordem) e só grava se as
    duas passarem. Se qualquer uma levantar ``ValueError``, NADA é gravado -- nem a política,
    nem o orçamento (que este módulo, aliás, nunca escreve aqui)."""
    validate_policy(candidate_policy)
    enforce(budget, candidate_policy)
    return save_policy(vault_path, candidate_policy)
