"""Alertas macro por regra explícita: o que mudou no ambiente, dito com o número e a janela.

São alertas INFORMATIVOS. Nenhuma regra aqui decide, sugere ou altera aporte, peso-alvo ou
rebalanceamento (o módulo não importa essas camadas; há teste de importação), e um alerta ativo
nunca faz o job falhar. Toda mensagem termina com o aviso de que é contexto.

As regras não moram no código: vivem em ``07_Research/Macro/alertas_macro.json``, com versão e
hash do conteúdo, que cada alerta carrega. ``DEFAULT_RULES`` é o ponto de partida editável; os
limiares são parâmetros de MONITORAMENTO, não política pessoal nem juízo sobre investimentos.
Um arquivo que existe mas está errado (JSON inválido, regra ou chave desconhecida, limiar
absurdo) levanta ``ValueError`` com o motivo: nunca cai em silêncio para o padrão.

Tipos de regra (o que se mede em cada observação da série):
  - ``window_change``: variação contra a última observação de N dias antes (séries diárias),
    em p.p. (``pp``) ou em % (``pct``). ``direction``: ``both``, ``up`` ou ``down``.
  - ``yoy_change``: variação contra a mesma competência de 12 meses antes (mensais/trimestrais).
  - ``level_above`` / ``level_below``: o nível do indicador contra o limiar.
  - ``level_change``: o nível mudou em relação à observação anterior (um EVENTO, como uma
    decisão do Copom).

Confirmação: ``confirmations`` = N observações VÁLIDAS E DISTINTAS da série (N competências ou
datas diferentes), todas com a condição verdadeira. Rodar o job duas vezes sobre o mesmo dado
não confirma nada: a série é a mesma.

Revisão não é competência nova: a condição é avaliada também sobre o PRIMEIRO valor coletado de
cada competência. Se ela só existe com o valor revisado, o alerta aparece marcado ``por
revisão`` e não gera notificação.

Rearme (evita reavisar quando o valor oscila em torno do limiar): depois de emitido, o alerta
só pode ser emitido de novo quando a medida volta ``rearm_fraction`` (20%) aquém do limiar.
  - limite bilateral (``both``): o rearme vale para o lado que disparou; se a medida passar
    direto para o lado oposto, é um alerta novo.
  - ``up``/``down`` e ``level_above``/``level_below``: rearma quando a medida recua 20% do
    limiar para dentro (no nível, o limiar menos 20% dele; no ``below``, mais 20%).
  - ``level_change`` ("qualquer alteração"): não há rearme; cada mudança é um evento com
    identidade própria (competência em que o nível mudou e o novo nível), emitido uma vez, e
    sai da lista depois de ``retain_days``.
Entre disparar e rearmar, o alerta deixa a lista de ativos quando a condição deixa de valer, e
fica em "em observação" até rearmar.

Avisos de dado (atraso, ausência, divergência entre fontes) vêm do contexto macro, ficam
separados dos alertas econômicos e nunca notificam.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import statistics
import string
from dataclasses import dataclass, field
from pathlib import Path

from iip.macro.context import MacroContext, _shift, build_context
from iip.macro.contract import DAILY, INDICATORS
from iip.macro.scenarios import Scenario, ScenarioSet
from iip.macro.sensitivity import analyse_asset
from iip.macro.store import MacroStore
from iip.portfolio.valuation_inputs import ValuationInputs

RULES_RELATIVE_PATH = Path("07_Research") / "Macro" / "alertas_macro.json"
STATE_RELATIVE_PATH = Path("07_Research") / "Macro" / "estado_alertas.json"

WINDOW_CHANGE, YOY_CHANGE = "window_change", "yoy_change"
LEVEL_ABOVE, LEVEL_BELOW, LEVEL_CHANGE = "level_above", "level_below", "level_change"
KINDS = (WINDOW_CHANGE, YOY_CHANGE, LEVEL_ABOVE, LEVEL_BELOW, LEVEL_CHANGE)
CHANGE_KINDS = (WINDOW_CHANGE, YOY_CHANGE)
DIRECTIONS = ("both", "up", "down")
UNITS = ("pp", "pct")
SEVERITY_ATTENTION, SEVERITY_INFO, SEVERITY_DATA = "atencao", "informativo", "dado"
SEVERITIES = (SEVERITY_ATTENTION, SEVERITY_INFO)
IMPACT_NTNB = "ntnb_valuation"

# a observação de comparação de uma janela pode estar até tantos dias antes da data-alvo (fim
# de semana, feriado); mais que isso é buracos na série e a comparação não vale
MAX_BASE_GAP_DAYS = 7
_ROUND = 6  # 0,2999999999 de erro de ponto flutuante não pode ficar abaixo de 0,30
_EPSILON = 1e-9

# a frase que fecha toda mensagem; não é configurável, de propósito
CONTEXT_NOTICE = "Contexto; não altera aporte nem peso."

MESSAGE_FIELDS = frozenset(
    {
        "value",
        "base",
        "change",
        "threshold",
        "window",
        "direction_verb",
        "reference",
        "base_reference",
        "from_value",
        "to_value",
    }
)
_RULE_KEYS = frozenset(
    {
        "id",
        "indicator",
        "kind",
        "severity",
        "message",
        "threshold",
        "unit",
        "window_days",
        "direction",
        "confirmations",
        "retain_days",
        "impact",
        "description",
    }
)
_ROOT_KEYS = frozenset(
    {"type", "version", "origin", "rearm_fraction", "data_quality", "rules"}
)
_DATA_QUALITY_KEYS = ("stale", "missing", "divergence")


@dataclass(frozen=True)
class AlertRule:
    id: str
    indicator: str
    kind: str
    severity: str
    message: str
    threshold: float | None = None
    unit: str = ""
    window_days: int | None = None
    direction: str = "both"
    confirmations: int = 1
    retain_days: int = 14
    impact: str | None = None
    description: str = ""


@dataclass(frozen=True)
class DataQuality:
    stale: bool = True
    missing: bool = True
    divergence: bool = True


@dataclass(frozen=True)
class RuleSet:
    version: str
    origin: str
    rules: tuple[AlertRule, ...] = field(default_factory=tuple)
    rearm_fraction: float = 0.2
    data_quality: DataQuality = field(default_factory=DataQuality)

    @property
    def content_hash(self) -> str:
        """Hash do que define os resultados: versão, regras, fração de rearme e avisos de
        dado. A descrição (só documentação) fica de fora. Duas rodadas com o mesmo hash
        usaram exatamente as mesmas regras."""
        canonical = json.dumps(
            {
                "version": self.version,
                "rearm_fraction": self.rearm_fraction,
                "data_quality": [
                    getattr(self.data_quality, k) for k in _DATA_QUALITY_KEYS
                ],
                "rules": [_rule_payload(r, documentation=False) for r in self.rules],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


DEFAULT_RULES = RuleSet(
    version="2026-09-20.1",
    origin=(
        "conjunto-padrão do IIP, ponto de partida editável; os limiares são parâmetros de "
        "monitoramento, não política pessoal nem juízo sobre investimentos"
    ),
    rules=(
        AlertRule(
            "ntnb_real_30d",
            "ntnb_longa_real",
            WINDOW_CHANGE,
            SEVERITY_ATTENTION,
            "Taxa real da NTN-B longa {direction_verb} {change} em {window} dias (de {base}% "
            "em {base_reference} para {value}% em {reference}). É a taxa que o Bazin e o "
            "Yield usam.",
            threshold=0.30,
            unit="pp",
            window_days=30,
            confirmations=2,
            impact=IMPACT_NTNB,
            description="Movimento da taxa real que alimenta o retorno exigido dos modelos.",
        ),
        AlertRule(
            "selic_meta_mudou",
            "selic_meta",
            LEVEL_CHANGE,
            SEVERITY_ATTENTION,
            "Meta Selic alterada de {from_value}% para {to_value}% ao ano (a partir de "
            "{reference}).",
            description="Mudança de nível da meta: um evento do Copom, emitido uma vez.",
        ),
        AlertRule(
            "ipca_12m_acima",
            "ipca_12m",
            LEVEL_ABOVE,
            SEVERITY_ATTENTION,
            "IPCA em 12 meses ({value}% em {reference}) acima do limiar de monitoramento "
            "configurado ({threshold}%).",
            threshold=4.5,
            description="Referência de acompanhamento da inflação (3% de meta + 1,5 p.p. de "
            "tolerância), revisável; ultrapassá-la não indica ação na carteira.",
        ),
        AlertRule(
            "inadimplencia_12m",
            "inadimplencia_total",
            YOY_CHANGE,
            SEVERITY_INFO,
            "Inadimplência da carteira de crédito em {value}% ({reference}), {change} sobre "
            "12 meses antes (limiar de monitoramento: +{threshold} p.p.).",
            threshold=1.0,
            unit="pp",
            direction="up",
        ),
        AlertRule(
            "desocupacao_12m",
            "desocupacao_mensal",
            YOY_CHANGE,
            SEVERITY_INFO,
            "Desocupação em {value}% ({reference}), {change} sobre 12 meses antes (limiar "
            "de monitoramento: +{threshold} p.p.).",
            threshold=0.5,
            unit="pp",
            direction="up",
        ),
        AlertRule(
            "usd_30d",
            "usd_venda",
            WINDOW_CHANGE,
            SEVERITY_INFO,
            "Dólar {direction_verb} {change} em {window} dias (de R$ {base} em "
            "{base_reference} para R$ {value} em {reference}).",
            threshold=5.0,
            unit="pct",
            window_days=30,
            confirmations=2,
        ),
    ),
)


# --- as regras: validação, gravação e leitura ----------------------------------------------


def _rule_payload(rule: AlertRule, *, documentation: bool = True) -> dict:
    payload = {
        "id": rule.id,
        "indicator": rule.indicator,
        "kind": rule.kind,
        "severity": rule.severity,
        "message": rule.message,
        "confirmations": rule.confirmations,
    }
    if rule.threshold is not None:
        payload["threshold"] = rule.threshold
    if rule.unit:
        payload["unit"] = rule.unit
    if rule.window_days is not None:
        payload["window_days"] = rule.window_days
    if rule.kind in CHANGE_KINDS:
        payload["direction"] = rule.direction
    if rule.kind == LEVEL_CHANGE:
        payload["retain_days"] = rule.retain_days
    if rule.impact:
        payload["impact"] = rule.impact
    if documentation and rule.description:
        payload["description"] = rule.description
    return payload


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _fail(rule_id: str, reason: str) -> ValueError:
    return ValueError(f"regra {rule_id!r}: {reason}")


def _validate_message(rule: AlertRule) -> None:
    try:
        names = {
            name
            for _, name, _, _ in string.Formatter().parse(rule.message)
            if name is not None
        }
    except ValueError as exc:
        raise _fail(rule.id, f"mensagem mal formada ({exc})") from exc
    unknown = names - MESSAGE_FIELDS
    if unknown:
        raise _fail(
            rule.id,
            f"a mensagem usa campo desconhecido {sorted(unknown)} "
            f"(campos: {', '.join(sorted(MESSAGE_FIELDS))})",
        )


def _validate_rule(
    rule: AlertRule,
) -> None:  # noqa: C901 - uma checagem por regra do contrato
    if not rule.id.strip():
        raise ValueError("regra sem id")
    indicator = INDICATORS.get(rule.indicator)
    if indicator is None:
        raise _fail(rule.id, f"indicador fora do catálogo: {rule.indicator!r}")
    if indicator.accumulates_in_month:
        raise _fail(
            rule.id,
            f"{rule.indicator} acumula no mês (o mês em curso é parcial): não serve para regra",
        )
    if rule.kind not in KINDS:
        raise _fail(
            rule.id, f"tipo desconhecido {rule.kind!r} (tipos: {', '.join(KINDS)})"
        )
    if rule.severity not in SEVERITIES:
        raise _fail(
            rule.id, f"severidade {rule.severity!r} (use {' ou '.join(SEVERITIES)})"
        )
    if not _is_int(rule.confirmations) or not 1 <= rule.confirmations <= 30:
        raise _fail(rule.id, "confirmations precisa ser um inteiro de 1 a 30")
    _validate_message(rule)

    if rule.kind == LEVEL_CHANGE:
        if rule.threshold is not None or rule.unit or rule.window_days is not None:
            raise _fail(rule.id, "level_change não usa threshold, unit nem window_days")
        if not _is_int(rule.retain_days) or not 1 <= rule.retain_days <= 90:
            raise _fail(rule.id, "retain_days precisa ser um inteiro de 1 a 90")
    else:
        if rule.threshold is None or not math.isfinite(rule.threshold):
            raise _fail(rule.id, "falta um threshold numérico")
        if rule.kind in CHANGE_KINDS and rule.threshold <= 0:
            raise _fail(rule.id, "o threshold de uma variação precisa ser positivo")
    if rule.kind in CHANGE_KINDS:
        if rule.unit not in UNITS:
            raise _fail(rule.id, f"unit {rule.unit!r} (use {' ou '.join(UNITS)})")
        if rule.direction not in DIRECTIONS:
            raise _fail(
                rule.id, f"direction {rule.direction!r} (use {', '.join(DIRECTIONS)})"
            )
        if rule.unit == "pct" and rule.threshold > 100:
            raise _fail(rule.id, "threshold em % acima de 100: confira a unidade")
    elif rule.direction != "both":
        raise _fail(rule.id, "direction só vale para regras de variação")
    if rule.kind == WINDOW_CHANGE:
        if indicator.frequency != DAILY:
            raise _fail(rule.id, "window_change só vale para séries diárias")
        if not _is_int(rule.window_days) or not 1 <= rule.window_days <= 365:
            raise _fail(rule.id, "window_days precisa ser um inteiro de 1 a 365")
    elif rule.window_days is not None:
        raise _fail(rule.id, "window_days só vale para window_change")
    if rule.kind == YOY_CHANGE and indicator.change_kind != rule.unit:
        raise _fail(
            rule.id,
            f"{rule.indicator} compara 12 meses em {indicator.change_kind!r}, não em "
            f"{rule.unit!r}",
        )
    if rule.impact is not None:
        if rule.impact != IMPACT_NTNB:
            raise _fail(rule.id, f"impact desconhecido {rule.impact!r}")
        if rule.indicator != "ntnb_longa_real" or rule.unit != "pp":
            raise _fail(
                rule.id, "impact só vale para variação em p.p. de ntnb_longa_real"
            )


def validate(rule_set: RuleSet) -> None:
    """Levanta ``ValueError`` com o motivo se o conjunto não serve."""
    if not rule_set.version.strip():
        raise ValueError("o conjunto de regras precisa de uma versão")
    if not rule_set.rules:
        raise ValueError("o conjunto de regras está vazio")
    fraction = rule_set.rearm_fraction
    if (
        isinstance(fraction, bool)
        or not isinstance(fraction, float | int)
        or not 0 < fraction < 1
    ):
        raise ValueError("rearm_fraction precisa estar entre 0 e 1 (exclusive)")
    seen: set[str] = set()
    for rule in rule_set.rules:
        if rule.id in seen:
            raise _fail(rule.id, "id repetido")
        seen.add(rule.id)
        _validate_rule(rule)


def _to_payload(rule_set: RuleSet) -> dict:
    return {
        "type": "macro_alert_rules",
        "version": rule_set.version,
        "origin": rule_set.origin,
        "rearm_fraction": rule_set.rearm_fraction,
        "data_quality": {
            k: getattr(rule_set.data_quality, k) for k in _DATA_QUALITY_KEYS
        },
        "rules": [_rule_payload(r) for r in rule_set.rules],
    }


def save_rules(vault_path: str | Path, rule_set: RuleSet) -> Path:
    validate(rule_set)
    path = Path(vault_path) / RULES_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_payload(rule_set), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _parse_rule(item: object) -> AlertRule:
    if not isinstance(item, dict):
        raise ValueError(f"regra mal formada (não é um objeto): {item!r}")
    label = item.get("id", "?")
    unknown = set(item) - _RULE_KEYS
    if unknown:
        raise _fail(str(label), f"chave desconhecida {sorted(unknown)}")
    missing = [
        k for k in ("id", "indicator", "kind", "severity", "message") if k not in item
    ]
    if missing:
        raise _fail(str(label), f"faltam as chaves {missing}")
    try:
        return AlertRule(
            id=str(item["id"]),
            indicator=str(item["indicator"]),
            kind=str(item["kind"]),
            severity=str(item["severity"]),
            message=str(item["message"]),
            threshold=(
                None if item.get("threshold") is None else float(item["threshold"])
            ),
            unit=str(item.get("unit", "")),
            window_days=item.get("window_days"),
            direction=str(item.get("direction", "both")),
            confirmations=item.get("confirmations", 1),
            retain_days=item.get("retain_days", 14),
            impact=item.get("impact"),
            description=str(item.get("description", "")),
        )
    except (TypeError, ValueError) as exc:
        raise _fail(str(label), f"valor mal formado ({exc})") from exc


def load_rules(vault_path: str | Path) -> RuleSet | None:
    """O conjunto gravado no vault, ou ``None`` se não há arquivo. Um arquivo que existe mas
    está errado levanta ``ValueError`` com o motivo: nunca cai em silêncio para o padrão.
    """
    path = Path(vault_path) / RULES_RELATIVE_PATH
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
        quality_raw = raw.get("data_quality", {})
        if not isinstance(quality_raw, dict) or set(quality_raw) - set(
            _DATA_QUALITY_KEYS
        ):
            raise ValueError(f"data_quality aceita só {list(_DATA_QUALITY_KEYS)}")
        if any(not isinstance(v, bool) for v in quality_raw.values()):
            raise ValueError("data_quality só aceita true ou false")
        rule_set = RuleSet(
            version=str(raw["version"]),
            origin=str(raw.get("origin", "")),
            rearm_fraction=raw.get("rearm_fraction", 0.2),
            data_quality=DataQuality(**quality_raw),
            rules=tuple(_parse_rule(item) for item in raw["rules"]),
        )
        validate(rule_set)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{path}: regras mal formadas ({exc!r})") from exc
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return rule_set


# --- a medição -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Measure:
    """O que se mediu numa observação: o valor, contra que observação e o resultado."""

    reference: str
    value: float
    base_reference: str | None = None
    base_value: float | None = None
    measure: float | None = None  # a quantidade comparada com o limiar (com sinal)


@dataclass(frozen=True)
class RuleEvaluation:
    rule: AlertRule
    status: str  # sem_alerta | ativo | sem_dados | defasado | insuficiente
    latest: Measure | None = None
    direction: str | None = None  # up | down | above | below
    confirmed_references: tuple[str, ...] = ()
    by_revision: bool = False
    event_key: str | None = None
    event_from: float | None = None
    event_to: float | None = None
    event_reference: str | None = None


def _series(store: MacroStore, indicator_id: str, view: str) -> list[tuple[str, float]]:
    """(competência, valor) distintos, em ordem. ``latest``: o valor mais recente de cada
    competência; ``first``: o primeiro valor coletado dela (antes de qualquer revisão).
    """
    if view == "first":
        chosen: dict[str, float] = {}
        for obs in store.observations(indicator_id):
            if obs.value is not None and obs.reference not in chosen:
                chosen[obs.reference] = obs.value
    else:
        chosen = {
            o.reference: o.value
            for o in store.latest(indicator_id)
            if o.value is not None
        }
    return sorted(chosen.items())


def _base_observation(
    rule: AlertRule, frequency: str, observations: list[tuple[str, float]], index: int
) -> tuple[str, float] | None:
    reference = observations[index][0]
    earlier = observations[:index]
    if rule.kind == WINDOW_CHANGE:
        target = (
            _dt.date.fromisoformat(reference) - _dt.timedelta(days=rule.window_days)
        ).isoformat()
        candidates = [o for o in earlier if o[0] <= target]
        if not candidates:
            return None
        gap = (
            _dt.date.fromisoformat(target) - _dt.date.fromisoformat(candidates[-1][0])
        ).days
        return candidates[-1] if gap <= MAX_BASE_GAP_DAYS else None
    target = _shift(reference, frequency)
    if frequency == DAILY:
        candidates = [o for o in earlier if o[0] <= target]
        return candidates[-1] if candidates else None
    return next((o for o in earlier if o[0] == target), None)


def _measure_at(
    rule: AlertRule, observations: list[tuple[str, float]], index: int
) -> Measure | None:
    reference, value = observations[index]
    if rule.kind in (LEVEL_ABOVE, LEVEL_BELOW):
        return Measure(reference, value, measure=value)
    frequency = INDICATORS[rule.indicator].frequency
    base = _base_observation(rule, frequency, observations, index)
    if base is None:
        return None
    if rule.unit == "pp":
        change = value - base[1]
    else:
        if base[1] == 0:
            return None
        change = (value / base[1] - 1) * 100
    return Measure(reference, value, base[0], base[1], round(change, _ROUND))


def _holds(rule: AlertRule, measure: float) -> bool:
    threshold = rule.threshold
    if rule.kind == LEVEL_ABOVE:
        return measure > threshold + _EPSILON
    if rule.kind == LEVEL_BELOW:
        return measure < threshold - _EPSILON
    if rule.direction == "up":
        return measure >= threshold - _EPSILON
    if rule.direction == "down":
        return measure <= -threshold + _EPSILON
    return abs(measure) >= threshold - _EPSILON


def _side(rule: AlertRule, measure: float) -> str:
    if rule.kind == LEVEL_ABOVE:
        return "above"
    if rule.kind == LEVEL_BELOW:
        return "below"
    return "up" if measure > 0 else "down"


def _evaluate_state_rule(
    rule: AlertRule, observations: list[tuple[str, float]]
) -> RuleEvaluation:
    latest = _measure_at(rule, observations, len(observations) - 1)
    n = rule.confirmations
    if latest is None or len(observations) < n:
        last_ref, last_value = observations[-1]
        return RuleEvaluation(rule, "insuficiente", Measure(last_ref, last_value))
    window = [
        _measure_at(rule, observations, i)
        for i in range(len(observations) - n, len(observations))
    ]
    if any(m is None for m in window):
        return RuleEvaluation(rule, "insuficiente", latest)
    sides = {_side(rule, m.measure) for m in window}
    if all(_holds(rule, m.measure) for m in window) and len(sides) == 1:
        return RuleEvaluation(
            rule,
            "ativo",
            latest,
            direction=sides.pop(),
            confirmed_references=tuple(m.reference for m in window),
        )
    return RuleEvaluation(rule, "sem_alerta", latest)


def _last_change(
    observations: list[tuple[str, float]],
) -> tuple[int, float, float] | None:
    for index in range(len(observations) - 1, 0, -1):
        before, after = observations[index - 1][1], observations[index][1]
        if abs(after - before) > _EPSILON:
            return index, before, after
    return None


def _evaluate_event_rule(
    rule: AlertRule, observations: list[tuple[str, float]], today: _dt.date
) -> RuleEvaluation:
    last_ref, last_value = observations[-1]
    latest = Measure(last_ref, last_value)
    change = _last_change(observations)
    if change is None:
        return RuleEvaluation(rule, "sem_alerta", latest)
    index, before, after = change
    reference = observations[index][0]
    key = f"{reference}:{after:g}"
    age = (today - _dt.date.fromisoformat(reference)).days
    confirmed = len(observations) - index >= rule.confirmations
    status = "ativo" if confirmed and age <= rule.retain_days else "sem_alerta"
    return RuleEvaluation(
        rule,
        status,
        latest,
        direction="above" if after > before else "below",
        confirmed_references=tuple(o[0] for o in observations[index:]),
        event_key=key,
        event_from=before,
        event_to=after,
        event_reference=reference,
    )


def _evaluate_view(
    rule: AlertRule, observations: list[tuple[str, float]], today: _dt.date
) -> RuleEvaluation:
    if not observations:
        return RuleEvaluation(rule, "sem_dados")
    if rule.kind == LEVEL_CHANGE:
        return _evaluate_event_rule(rule, observations, today)
    return _evaluate_state_rule(rule, observations)


def evaluate_rule(
    rule: AlertRule, store: MacroStore, today: _dt.date, *, stale: bool
) -> RuleEvaluation:
    latest_view = _evaluate_view(rule, _series(store, rule.indicator, "latest"), today)
    if latest_view.status == "sem_dados":
        return latest_view
    if stale:
        # dado velho não vira alerta de hoje; o aviso de dado explica o atraso
        return RuleEvaluation(rule, "defasado", latest_view.latest)
    if latest_view.status != "ativo":
        return latest_view
    first_view = _evaluate_view(rule, _series(store, rule.indicator, "first"), today)
    same = (
        first_view.status == "ativo"
        and first_view.direction == latest_view.direction
        and first_view.event_key == latest_view.event_key
    )
    return RuleEvaluation(
        rule,
        "ativo",
        latest_view.latest,
        direction=latest_view.direction,
        confirmed_references=latest_view.confirmed_references,
        by_revision=not same,
        event_key=latest_view.event_key,
        event_from=latest_view.event_from,
        event_to=latest_view.event_to,
        event_reference=latest_view.event_reference,
    )


# --- o rearme ------------------------------------------------------------------------------


def _rearmed(
    rule: AlertRule, evaluation: RuleEvaluation, side: str | None, fraction: float
) -> bool:
    """A medida voltou ``fraction`` do limiar para dentro? Sem medida, não rearma."""
    latest = evaluation.latest
    if latest is None or latest.measure is None or rule.threshold is None:
        return False
    measure, threshold = latest.measure, rule.threshold
    margin = fraction * abs(threshold)
    if rule.kind == LEVEL_ABOVE:
        return measure <= threshold - margin
    if rule.kind == LEVEL_BELOW:
        return measure >= threshold + margin
    inner = (1 - fraction) * threshold
    if side == "up":
        return measure <= inner
    if side == "down":
        return measure >= -inner
    return abs(measure) <= inner


# --- os alertas ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Alert:
    key: str
    category: str  # economico | dado
    severity: str  # atencao | informativo | dado
    rule_id: str | None
    indicator: str
    message: str  # já com o aviso de contexto
    reference: str | None  # a competência (ou data) da observação que disparou
    since: str  # o dia em que o alerta foi visto pela primeira vez
    is_new: bool
    by_revision: bool = False
    trace: dict = field(default_factory=dict)
    impact: tuple[str, ...] = ()

    @property
    def notifies(self) -> bool:
        return (
            self.is_new
            and self.category == "economico"
            and self.severity == SEVERITY_ATTENTION
            and not self.by_revision
        )


@dataclass(frozen=True)
class Watching:
    """Já emitido e fora da condição, mas ainda não rearmado."""

    rule_id: str
    indicator: str
    measure: float | None
    threshold: float | None
    since: str | None


@dataclass(frozen=True)
class AlertRun:
    today: _dt.date
    rules: RuleSet
    evaluations: tuple[RuleEvaluation, ...]
    active: tuple[Alert, ...]
    watching: tuple[Watching, ...]
    data_alerts: tuple[Alert, ...]
    state: dict

    @property
    def new_alerts(self) -> tuple[Alert, ...]:
        return tuple(a for a in (*self.active, *self.data_alerts) if a.is_new)

    @property
    def notifiable(self) -> tuple[Alert, ...]:
        return tuple(a for a in self.active if a.notifies)


def _num(value: float | None) -> str:
    """Número em pt-BR, com no mínimo 2 e no máximo 4 casas."""
    if value is None:
        return "—"
    text = f"{value:.4f}".rstrip("0")
    whole, _, decimals = text.partition(".")
    return f"{whole},{decimals.ljust(2, '0')}"


def _signed(value: float, unit: str) -> str:
    text = f"{abs(value):.2f}".replace(".", ",")
    sign = "+" if value >= 0 else "-"
    return f"{sign}{text} p.p." if unit == "pp" else f"{sign}{text}%"


def _label(reference: str | None) -> str:
    """A data diária em dd/mm/aaaa; a competência mensal ou trimestral como está."""
    if reference and len(reference) == 10:
        return _dt.date.fromisoformat(reference).strftime("%d/%m/%Y")
    return reference or "—"


def render_message(rule: AlertRule, evaluation: RuleEvaluation) -> str:
    latest = evaluation.latest
    change = latest.measure if latest else None
    fields = {
        "value": _num(latest.value) if latest else "—",
        "base": _num(latest.base_value) if latest else "—",
        "change": _signed(change, rule.unit) if change is not None else "—",
        "threshold": _num(rule.threshold),
        "window": str(rule.window_days) if rule.window_days else "—",
        "direction_verb": "subiu" if (change or 0) >= 0 else "caiu",
        "reference": _label(
            evaluation.event_reference or (latest.reference if latest else None)
        ),
        "base_reference": _label(latest.base_reference if latest else None),
        "from_value": _num(evaluation.event_from),
        "to_value": _num(evaluation.event_to),
    }
    return f"{rule.message.format(**fields)} {CONTEXT_NOTICE}"


def _method_label(method: str) -> str:
    return {"bazin": "Bazin", "yield": "Yield"}.get(method, method)


def ntnb_impact(inputs: ValuationInputs | None, shift_pp: float) -> tuple[str, ...]:
    """O que um deslocamento da taxa real de ``shift_pp`` faz com o valor justo dos métodos que
    a usam, com o restante dos insumos igual. Reusa a análise da sensibilidade (mesmo
    avaliador do valuation); é estimativa das premissas, não previsão."""
    if inputs is None:
        return (
            "Impacto não estimado: sem insumos de valuation (`iip value-portfolio --report`).",
        )
    if inputs.base_rate is None:
        return ("Impacto não estimado: os insumos não têm a taxa-base da NTN-B.",)
    move = ScenarioSet(
        "impacto",
        "movimento observado",
        (Scenario("movimento", "movimento observado", real_yield_shock_pp=shift_pp),),
    )
    changes: dict[str, list[float]] = {}
    for position in inputs.positions:
        asset = analyse_asset(position, inputs.base_rate.real_yield, move)
        outcome = asset.scenarios[0]
        for index, base in enumerate(asset.base):
            if base.method not in asset.sensitive_methods or not base.fair_value:
                continue
            other = outcome.methods[index].fair_value
            if other is not None:
                changes.setdefault(base.method, []).append(
                    (other / base.fair_value - 1) * 100
                )
    if not changes:
        return ("Impacto não estimado: nenhum ativo dos insumos usa a taxa real.",)
    lines = []
    for method in sorted(changes):
        values = changes[method]
        lines.append(
            f"{_method_label(method)}: mediana {_signed(statistics.median(values), 'pct')} no "
            f"valor justo ({len(values)} ativos; de {_signed(min(values), 'pct')} a "
            f"{_signed(max(values), 'pct')})"
        )
    lines.append(
        f"Estimativa com os insumos de {inputs.run_date} e o restante igual; sensibilidade "
        "das premissas, não previsão."
    )
    return tuple(lines)


def _trace(rule_set: RuleSet, rule: AlertRule, evaluation: RuleEvaluation) -> dict:
    latest = evaluation.latest
    return {
        "regra": rule.id,
        "versao_regras": rule_set.version,
        "hash_regras": rule_set.content_hash,
        "indicador": rule.indicator,
        "tipo": rule.kind,
        "janela_dias": rule.window_days,
        "limiar": rule.threshold,
        "unidade": rule.unit or None,
        "sentido": rule.direction if rule.kind in CHANGE_KINDS else None,
        "confirmacoes": rule.confirmations,
        "competencias_confirmadas": list(evaluation.confirmed_references),
        "valor": latest.value if latest else None,
        "competencia": latest.reference if latest else None,
        "valor_base": latest.base_value if latest else None,
        "competencia_base": latest.base_reference if latest else None,
        "medida": latest.measure if latest else None,
        "nivel_anterior": evaluation.event_from,
        "nivel_novo": evaluation.event_to,
        "por_revisao": evaluation.by_revision,
    }


def _data_alerts(
    context: MacroContext, rule_set: RuleSet, previous: dict[str, str], today: _dt.date
) -> tuple[list[Alert], dict[str, str]]:
    quality = rule_set.data_quality
    found: list[tuple[str, str, str | None, str]] = (
        []
    )  # (chave, indicador, competência, motivo)
    for reading in context.readings:
        ind = reading.indicator
        if reading.missing and quality.missing:
            found.append(
                (
                    f"sem_dados:{ind.id}",
                    ind.id,
                    None,
                    f"{ind.name}: sem dados guardados.",
                )
            )
        elif reading.stale and quality.stale:
            found.append(
                (
                    f"defasado:{ind.id}",
                    ind.id,
                    reading.latest.reference,
                    f"{ind.name}: atrasado; a última competência é {reading.latest.reference} "
                    f"e o limite é {ind.stale_after_days} dias depois do fim dela.",
                )
            )
    if quality.divergence:
        for check in context.source_checks:
            if check.compared and not check.agrees:
                found.append(
                    (
                        f"divergencia:{check.a}|{check.b}",
                        check.a,
                        None,
                        f"Fontes divergem: {check.a} x {check.b} (maior diferença "
                        f"{_num(check.max_difference)} em {check.compared} competências).",
                    )
                )
    today_text = today.isoformat()
    state: dict[str, str] = {}
    alerts = []
    for key, indicator_id, reference, reason in found:
        since = previous.get(key, today_text)
        state[key] = since
        alerts.append(
            Alert(
                key,
                "dado",
                SEVERITY_DATA,
                None,
                indicator_id,
                reason,
                reference,
                since,
                is_new=key not in previous,
                trace={"motivo": key.split(":")[0], "indicador": indicator_id},
            )
        )
    return alerts, state


def run_alerts(
    store: MacroStore,
    rule_set: RuleSet,
    state: dict | None,
    today: _dt.date,
    *,
    inputs: ValuationInputs | None = None,
) -> AlertRun:
    """Avalia todas as regras sobre o que está guardado. Não usa rede e não grava nada: quem
    chama grava o estado devolvido (``AlertRun.state``)."""
    validate(rule_set)
    previous_rules = (state or {}).get("rules", {})
    previous_data = (state or {}).get("data", {})
    context = build_context(store, today)
    stale = {r.indicator.id: r.stale for r in context.readings}
    today_text = today.isoformat()

    evaluations: list[RuleEvaluation] = []
    active: list[Alert] = []
    watching: list[Watching] = []
    new_rules: dict[str, dict] = {}

    for rule in rule_set.rules:
        evaluation = evaluate_rule(
            rule, store, today, stale=stale.get(rule.indicator, False)
        )
        evaluations.append(evaluation)
        entry = dict(previous_rules.get(rule.id, {}))
        latched = bool(entry.get("latched"))

        if evaluation.status in ("sem_dados", "defasado", "insuficiente"):
            new_rules[rule.id] = (
                entry  # sem base para decidir: o estado fica como estava
            )
            if latched:
                watching.append(
                    Watching(
                        rule.id,
                        rule.indicator,
                        None,
                        rule.threshold,
                        entry.get("since"),
                    )
                )
            continue

        if rule.kind == LEVEL_CHANGE:
            is_active = evaluation.status == "ativo"
            is_new = is_active and entry.get("event_key") != evaluation.event_key
            if is_active:
                entry.update(event_key=evaluation.event_key)
                entry.setdefault("since", today_text)
                if is_new:
                    entry["since"] = today_text
            new_rules[rule.id] = entry
        else:
            is_active = evaluation.status == "ativo"
            is_new = is_active and (
                not latched or entry.get("direction") != evaluation.direction
            )
            if is_active:
                entry.update(
                    latched=True,
                    direction=evaluation.direction,
                    since=today_text if is_new else entry.get("since", today_text),
                )
            elif latched and _rearmed(
                rule, evaluation, entry.get("direction"), rule_set.rearm_fraction
            ):
                entry.update(latched=False, direction=None)
            elif latched:
                watching.append(
                    Watching(
                        rule.id,
                        rule.indicator,
                        evaluation.latest.measure if evaluation.latest else None,
                        rule.threshold,
                        entry.get("since"),
                    )
                )
            new_rules[rule.id] = entry

        if not is_active:
            continue
        impact: tuple[str, ...] = ()
        if (
            rule.impact == IMPACT_NTNB
            and evaluation.latest
            and evaluation.latest.measure is not None
        ):
            impact = ntnb_impact(inputs, evaluation.latest.measure)
        active.append(
            Alert(
                rule.id,
                "economico",
                rule.severity,
                rule.id,
                rule.indicator,
                render_message(rule, evaluation),
                evaluation.event_reference
                or (evaluation.latest.reference if evaluation.latest else None),
                new_rules[rule.id].get("since", today_text),
                is_new=is_new,
                by_revision=evaluation.by_revision,
                trace=_trace(rule_set, rule, evaluation),
                impact=impact,
            )
        )

    data_alerts, data_state = _data_alerts(context, rule_set, previous_data, today)
    new_state = {
        "type": "macro_alert_state",
        "date": today_text,
        "rules_version": rule_set.version,
        "rules_hash": rule_set.content_hash,
        "rules": new_rules,
        "data": data_state,
    }
    severity_order = {SEVERITY_ATTENTION: 0, SEVERITY_INFO: 1}
    active.sort(key=lambda a: (severity_order.get(a.severity, 9), a.key))
    return AlertRun(
        today,
        rule_set,
        tuple(evaluations),
        tuple(active),
        tuple(watching),
        tuple(data_alerts),
        new_state,
    )


# --- o estado e o arquivo de alerta --------------------------------------------------------


def load_state(vault_path: str | Path) -> dict | None:
    """O estado gravado, ou ``None`` na primeira execução. Um estado ilegível levanta
    ``ValueError``: recomeçar do zero em silêncio reavisaria tudo o que já foi avisado.
    """
    path = Path(vault_path) / STATE_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path}: estado dos alertas ilegível ({exc}); corrija ou apague o arquivo"
        ) from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("rules", {}), dict):
        raise ValueError(
            f"{path}: estado dos alertas mal formado; corrija ou apague o arquivo"
        )
    return raw


def save_state(vault_path: str | Path, state: dict) -> Path:
    path = Path(vault_path) / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def alert_lines(run: AlertRun) -> tuple[str, ...]:
    """Uma linha por alerta que pede notificação (novo, de Atenção e sem ser por revisão)."""
    lines = []
    for alert in run.notifiable:
        body = alert.message.removesuffix(f" {CONTEXT_NOTICE}")
        headline = next((i for i in alert.impact if not i.startswith("Estimativa")), "")
        lines.append(f"ATENCAO {body}" + (f" [{headline}]" if headline else ""))
    return tuple(lines)


def write_alert_file(path: Path | str, run: AlertRun) -> tuple[str, ...]:
    """Grava as linhas em ``path`` (UTF-8) ou, sem alerta novo, apaga o de uma rodada
    anterior. O arquivo é o que o agendador lê para a notificação do Windows."""
    target = Path(path)
    lines = alert_lines(run)
    if lines:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        target.unlink(missing_ok=True)
    return lines
