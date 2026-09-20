"""Sensibilidade dos valuations a cenários de juros e inflação.

Reavalia os MESMOS insumos da última rodada de ``value-portfolio`` (guardados por
``iip.portfolio.valuation_inputs``) com a taxa real da NTN-B deslocada por cada cenário, usando
``evaluate_valuations``, o avaliador que o resto do projeto já usa. Não há cópia da lógica de
valuation aqui: o que muda de um cenário para outro é uma única entrada, ``ntnb_real_yield``, e
o resultado sai do mesmo cálculo. Um método que não usa essa taxa (Graham, NAV) dá o mesmo valor
em todos os cenários e é dito insensível, por comparação e não por lista: se um dia outro método
passar a ler a taxa, ele aparece sensível sem mudar nada aqui.

Rastreabilidade: o resultado leva a versão deste modelo, os parâmetros dos modelos de valuation
(prêmio dos FIIs, exigências do Bazin), a versão e o hash dos cenários, a taxa-base com fonte,
data de referência e a observação correspondente no armazenamento macro (com a data em que foi
coletada), a data da rodada dos insumos e os avisos de datas e unidades.

O resultado é SENSIBILIDADE das premissas. Não é recomendação, e nada daqui altera aporte,
peso-alvo ou rebalanceamento (o módulo não importa nada dessas camadas).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from iip.macro.scenarios import (
    SCENARIO_RULE_VERSION,
    TRANSMISSION_RULE,
    ScenarioSet,
)
from iip.macro.store import MacroStore
from iip.portfolio.valuation_inputs import BaseRate, ValuationInputs
from iip.portfolio_data import valuation_methods as vm

SENSITIVITY_MODEL_VERSION = "macro-sensibilidade-1"

# insumos com mais de tantos dias: o resultado descreve preços e dividendos de outro momento
MAX_INPUT_AGE_DAYS = 7
# taxa-base com data de referência mais de tantos dias antes da rodada: avisa
MAX_RATE_LAG_DAYS = 5
_TOLERANCE = 1e-9

# classes cujo valuation depende de outro valuation feito com a taxa da rodada
_UPSTREAM_NOTE = {
    "fmp_fgts": (
        "a transparência usa a margem das ações subjacentes, calculada com a taxa da rodada; "
        "ela não é recalculada aqui, então este ativo não tem sensibilidade calculada"
    )
}


@dataclass(frozen=True)
class MethodValue:
    method: str
    status: str
    fair_value: float | None
    margin: float | None
    detail: str = ""


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario_id: str
    real_yield: float | None  # a taxa real do cenário (fração)
    methods: tuple[MethodValue, ...]


@dataclass(frozen=True)
class AssetSensitivity:
    ticker: str
    asset_class: str
    price: float | None
    base: tuple[MethodValue, ...]
    scenarios: tuple[ScenarioOutcome, ...]
    sensitive_methods: tuple[str, ...]
    insensitive_methods: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class RateObservation:
    """A observação da taxa no armazenamento macro (proveniência)."""

    reference: str
    value_pct: float
    collected_at: str
    note: str


@dataclass(frozen=True)
class SensitivityResult:
    model_version: str
    model_parameters: dict[str, float]
    scenario_version: str
    scenario_hash: str
    scenario_origin: str
    transmission: str
    base_rate: BaseRate | None
    stored_observation: RateObservation | None  # a do dia da taxa-base
    newer_observation: (
        RateObservation | None
    )  # uma mais nova que a da rodada, se houver
    inputs_run_date: str
    today: str
    warnings: tuple[str, ...]
    scenarios: tuple[
        tuple[str, str, float], ...
    ]  # (id, nome, deslocamento da real, p.p.)
    assets: tuple[AssetSensitivity, ...]


def model_parameters() -> dict[str, float]:
    """Os parâmetros dos modelos de valuation que entram nas contas de Bazin e Yield."""
    return {
        "FII_YIELD_RISK_PREMIUM": vm.FII_YIELD_RISK_PREMIUM,
        "BAZIN_MIN_CONSISTENCY_YEARS": vm.BAZIN_MIN_CONSISTENCY_YEARS,
        "BAZIN_MAX_PAYOUT_PCT": vm.BAZIN_MAX_PAYOUT_PCT,
        "FII_MAX_SUSTAINABLE_YIELD_PCT": vm.FII_MAX_SUSTAINABLE_YIELD_PCT,
    }


def _method_values(attempts) -> tuple[MethodValue, ...]:
    values = []
    for attempt in attempts:
        snapshot = attempt.snapshot
        values.append(
            MethodValue(
                attempt.method.value,
                attempt.status,
                snapshot.fair_value if snapshot else None,
                snapshot.margin_of_safety if snapshot else None,
                attempt.reason or "",
            )
        )
    return tuple(values)


def _differs(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return abs(a - b) > _TOLERANCE


def _evaluate(position, rate: float | None, exceptions=None):
    inputs = dict(position.inputs)
    inputs["ntnb_real_yield"] = rate
    return vm.evaluate_valuations(
        ticker=position.ticker,
        asset_class=position.asset_class,
        sector=position.sector,
        industry=position.industry,
        price=position.price,
        inputs=inputs,
        exceptions=exceptions,
    )


def analyse_asset(
    position, base_rate: float | None, scenario_set: ScenarioSet, exceptions=None
) -> AssetSensitivity:
    base = _method_values(_evaluate(position, base_rate, exceptions))
    outcomes = []
    for scenario in scenario_set.scenarios:
        rate = (
            None
            if base_rate is None
            else base_rate + scenario.real_yield_shift_pp / 100.0
        )
        outcomes.append(
            ScenarioOutcome(
                scenario.id, rate, _method_values(_evaluate(position, rate, exceptions))
            )
        )
    sensitive, insensitive = [], []
    for index, base_value in enumerate(base):
        changed = any(
            _differs(base_value.fair_value, out.methods[index].fair_value)
            for out in outcomes
        )
        # só métodos que produziram valor na base ou em algum cenário entram na conta
        produced = base_value.fair_value is not None or any(
            out.methods[index].fair_value is not None for out in outcomes
        )
        if produced:
            (sensitive if changed else insensitive).append(base_value.method)
    return AssetSensitivity(
        position.ticker,
        position.asset_class,
        position.price,
        base,
        tuple(outcomes),
        tuple(sensitive),
        tuple(insensitive),
        note=_UPSTREAM_NOTE.get(position.asset_class, ""),
    )


def _observation(store: MacroStore | None, reference: str | None):
    """A observação da NTN-B no armazenamento macro para ``reference`` (ou a mais nova)."""
    if store is None:
        return None, None
    latest = [o for o in store.latest("ntnb_longa_real") if o.value is not None]
    if not latest:
        return None, None
    by_ref = {o.reference: o for o in latest}

    def wrap(o):
        return RateObservation(o.reference, o.value, o.collected_at, o.note)

    same = wrap(by_ref[reference]) if reference in by_ref else None
    newest = latest[-1]
    newer = wrap(newest) if reference is None or newest.reference > reference else None
    return same, newer


def run_sensitivity(
    inputs: ValuationInputs,
    scenario_set: ScenarioSet,
    *,
    store: MacroStore | None,
    today: _dt.date,
    exceptions=None,
) -> SensitivityResult:
    warnings: list[str] = []
    base = inputs.base_rate
    run_date = _dt.date.fromisoformat(inputs.run_date)
    if (today - run_date).days > MAX_INPUT_AGE_DAYS:
        warnings.append(
            f"os insumos são da rodada de {run_date:%d/%m/%Y} ({(today - run_date).days} "
            "dias): preços, dividendos e taxa descrevem aquele dia, não hoje"
        )
    if base is None:
        warnings.append(
            "a rodada não tinha a taxa da NTN-B: sem taxa-base, Bazin e Yield não são "
            "calculados em nenhum cenário"
        )
        stored = newer = None
    else:
        reference = _dt.date.fromisoformat(base.reference_date)
        if (run_date - reference).days > MAX_RATE_LAG_DAYS:
            warnings.append(
                f"a taxa-base é de {reference:%d/%m/%Y}, {(run_date - reference).days} dias "
                f"antes da rodada ({run_date:%d/%m/%Y}): datas diferentes na mesma conta"
            )
        stored, newer = _observation(store, base.reference_date)
        if newer is not None:
            warnings.append(
                f"há uma taxa mais nova no armazenamento macro ({newer.reference}: "
                f"{newer.value_pct:.2f}%); a base usa a da rodada ({base.reference_date}: "
                f"{base.real_yield:.2%}). Rode `iip value-portfolio --report` para alinhar"
            )
        if stored is None and store is not None:
            warnings.append(
                "a taxa-base não está no armazenamento macro (`iip collect-macro`): "
                "sem a data em que foi conhecida"
            )
        if (
            stored is not None
            and abs(stored.value_pct / 100.0 - base.real_yield) > 5e-5
        ):
            warnings.append(
                f"a taxa da rodada ({base.real_yield:.4%}) difere da guardada para o mesmo dia "
                f"({stored.value_pct:.4f}%)"
            )

    base_rate = base.real_yield if base else None
    assets = tuple(
        analyse_asset(position, base_rate, scenario_set, exceptions)
        for position in inputs.positions
    )
    for scenario in scenario_set.scenarios:
        if (
            base_rate is not None
            and base_rate + scenario.real_yield_shift_pp / 100.0 <= 0
        ):
            warnings.append(
                f"cenário {scenario.id}: a taxa real ficou <= 0; Bazin e Yield não se "
                "calculam com taxa não positiva"
            )
    return SensitivityResult(
        model_version=SENSITIVITY_MODEL_VERSION,
        model_parameters=model_parameters(),
        scenario_version=scenario_set.version,
        scenario_hash=scenario_set.content_hash,
        scenario_origin=scenario_set.origin,
        transmission=f"{SCENARIO_RULE_VERSION}: {TRANSMISSION_RULE}",
        base_rate=base,
        stored_observation=stored,
        newer_observation=newer,
        inputs_run_date=inputs.run_date,
        today=today.isoformat(),
        warnings=tuple(warnings),
        scenarios=tuple(
            (s.id, s.name, s.real_yield_shift_pp) for s in scenario_set.scenarios
        ),
        assets=assets,
    )
