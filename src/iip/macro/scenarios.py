"""Cenários de juros e inflação: parâmetros explícitos, versionados e reproduzíveis.

Um cenário é um CONJUNTO DE CHOQUES sobre a referência macro dos modelos de valuation. Os
choques não moram no código: vivem num arquivo do vault (``07_Research/Macro/cenarios.json``)
com uma versão e um hash do conteúdo, que os resultados carregam. O arquivo é criado a partir
do conjunto-padrão abaixo (``DEFAULT_SCENARIOS``), que é um PONTO DE PARTIDA para o usuário
editar, não uma previsão de ninguém.

O que os modelos usam do macro (hoje): só a taxa REAL da NTN-B longa, no Bazin (o retorno
exigido) e no Yield (a mesma taxa mais o prêmio dos FIIs). Por isso a regra de transmissão dos
choques para essa taxa é explícita e de primeira ordem:

    deslocamento da taxa real (p.p.) = choque na taxa nominal (p.p.)
                                       - choque na inflação esperada (p.p.)
                                       + choque direto na taxa real (p.p.)

É a identidade de Fisher aproximada: taxa real ~ nominal - inflação esperada. Ela entende
"juros sobem 1 p.p. com a inflação esperada igual" como taxa real +1 p.p.; "a inflação esperada
sobe 1 p.p. com o juro nominal igual" como taxa real -1 p.p.; e "os dois sobem 1 p.p." como
taxa real inalterada. NÃO modela: o efeito da inflação nos dividendos (o Bazin trata o
dividendo como já protegido da inflação), o do juro no lucro das empresas, nem o prêmio de
risco. É sensibilidade das PREMISSAS, não previsão.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

SCENARIO_RULE_VERSION = "fisher-1"
SCENARIOS_RELATIVE_PATH = Path("07_Research") / "Macro" / "cenarios.json"

# um choque acima disto (em p.p.) é quase certamente um erro de digitação (1000 em vez de 1,0)
MAX_ABS_SHOCK_PP = 15.0
RESERVED_IDS = frozenset({"base"})

TRANSMISSION_RULE = (
    "deslocamento da taxa real = choque nominal - choque de inflação esperada + choque direto "
    "na taxa real (p.p., primeira ordem, Fisher aproximado)"
)


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str = ""
    nominal_rate_shock_pp: float = 0.0
    inflation_shock_pp: float = 0.0
    real_yield_shock_pp: float = 0.0

    @property
    def real_yield_shift_pp(self) -> float:
        return (
            self.nominal_rate_shock_pp
            - self.inflation_shock_pp
            + self.real_yield_shock_pp
        )


@dataclass(frozen=True)
class ScenarioSet:
    version: str
    origin: str
    scenarios: tuple[Scenario, ...] = field(default_factory=tuple)

    @property
    def content_hash(self) -> str:
        """Hash do conteúdo que define os resultados: a versão, a regra de transmissão e os
        choques. Duas rodadas com o mesmo hash usaram exatamente os mesmos parâmetros.
        """
        canonical = json.dumps(
            {
                "version": self.version,
                "rule": SCENARIO_RULE_VERSION,
                "scenarios": [
                    [
                        s.id,
                        s.nominal_rate_shock_pp,
                        s.inflation_shock_pp,
                        s.real_yield_shock_pp,
                    ]
                    for s in self.scenarios
                ],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


DEFAULT_SCENARIOS = ScenarioSet(
    version="2026-09-20.1",
    origin=(
        "conjunto-padrão do IIP, ponto de partida editável; os choques são hipóteses de "
        "sensibilidade, não previsões"
    ),
    scenarios=(
        Scenario(
            "juros_alta_100",
            "Juros nominais +1,00 p.p.",
            "O juro nominal sobe 1 p.p. com a inflação esperada igual: a taxa real sobe 1 p.p.",
            nominal_rate_shock_pp=1.0,
        ),
        Scenario(
            "juros_queda_100",
            "Juros nominais -1,00 p.p.",
            "O juro nominal cai 1 p.p. com a inflação esperada igual: a taxa real cai 1 p.p.",
            nominal_rate_shock_pp=-1.0,
        ),
        Scenario(
            "inflacao_alta_100",
            "Inflação esperada +1,00 p.p. (juro nominal igual)",
            "A inflação esperada sobe 1 p.p. e o juro nominal não acompanha: a taxa real cai.",
            inflation_shock_pp=1.0,
        ),
        Scenario(
            "inflacao_e_juros_alta_100",
            "Inflação esperada e juros +1,00 p.p. (repasse integral)",
            "Os dois sobem 1 p.p.: a taxa real não muda. Mostra o que os modelos NÃO enxergam.",
            nominal_rate_shock_pp=1.0,
            inflation_shock_pp=1.0,
        ),
        Scenario(
            "estresse_juros_200",
            "Estresse: juros +2,00 p.p. e inflação esperada +0,50 p.p.",
            "Um choque de juros forte com a inflação esperada subindo pouco: taxa real +1,50 p.p.",
            nominal_rate_shock_pp=2.0,
            inflation_shock_pp=0.5,
        ),
    ),
)


def validate(scenario_set: ScenarioSet) -> None:
    """Levanta ``ValueError`` com o motivo se o conjunto não serve."""
    if not scenario_set.version.strip():
        raise ValueError("o conjunto de cenários precisa de uma versão")
    if not scenario_set.scenarios:
        raise ValueError("o conjunto de cenários está vazio")
    seen: set[str] = set()
    for s in scenario_set.scenarios:
        if not s.id.strip() or s.id in RESERVED_IDS:
            raise ValueError(f"id de cenário inválido ou reservado: {s.id!r}")
        if s.id in seen:
            raise ValueError(f"id de cenário repetido: {s.id!r}")
        seen.add(s.id)
        for label, value in (
            ("nominal_rate_shock_pp", s.nominal_rate_shock_pp),
            ("inflation_shock_pp", s.inflation_shock_pp),
            ("real_yield_shock_pp", s.real_yield_shock_pp),
        ):
            if abs(value) > MAX_ABS_SHOCK_PP:
                raise ValueError(
                    f"cenário {s.id}: {label}={value} passa de {MAX_ABS_SHOCK_PP} p.p. "
                    "(confira a unidade: o choque é em pontos percentuais)"
                )


def _to_payload(scenario_set: ScenarioSet) -> dict:
    return {
        "type": "macro_scenarios",
        "version": scenario_set.version,
        "origin": scenario_set.origin,
        "rule": SCENARIO_RULE_VERSION,
        "transmission": TRANSMISSION_RULE,
        "unit": "todos os choques em pontos percentuais",
        "scenarios": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "nominal_rate_shock_pp": s.nominal_rate_shock_pp,
                "inflation_shock_pp": s.inflation_shock_pp,
                "real_yield_shock_pp": s.real_yield_shock_pp,
            }
            for s in scenario_set.scenarios
        ],
    }


def save_scenarios(vault_path: str | Path, scenario_set: ScenarioSet) -> Path:
    validate(scenario_set)
    path = Path(vault_path) / SCENARIOS_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_payload(scenario_set), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_scenarios(vault_path: str | Path) -> ScenarioSet | None:
    """O conjunto gravado no vault, ou ``None`` se não há arquivo. Um arquivo que existe mas
    está errado levanta ``ValueError`` com o motivo: nunca cai em silêncio para o padrão.
    """
    path = Path(vault_path) / SCENARIOS_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: não é um JSON válido ({exc})") from exc
    if raw.get("rule") != SCENARIO_RULE_VERSION:
        raise ValueError(
            f"{path}: regra de transmissão {raw.get('rule')!r}, esperada "
            f"{SCENARIO_RULE_VERSION!r}"
        )
    try:
        scenario_set = ScenarioSet(
            version=str(raw["version"]),
            origin=str(raw.get("origin", "")),
            scenarios=tuple(
                Scenario(
                    id=item["id"],
                    name=item.get("name", item["id"]),
                    description=item.get("description", ""),
                    nominal_rate_shock_pp=float(item.get("nominal_rate_shock_pp", 0.0)),
                    inflation_shock_pp=float(item.get("inflation_shock_pp", 0.0)),
                    real_yield_shock_pp=float(item.get("real_yield_shock_pp", 0.0)),
                )
                for item in raw["scenarios"]
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path}: cenários mal formados ({exc})") from exc
    validate(scenario_set)
    return scenario_set
