"""Contrato do aporte proposto (APORTE_PROPOSTO_V1, revisão normativa 4.1):
``02_Portfolio/Aporte_Contrato.json``.

É o arquivo que o gerador de proposta (``aporte.py``) exige ``aprovada`` antes de calcular
qualquer coisa. Base: rev. 4 (SHA-256 do documento
``63bbeda126534b80716bf4b477bedc1d530db4c44d09dea2e47f91ebc905f7a0``), com a revisão 4.1 de
proveniência temporal do snapshot (especificação aprovada em 26/09/2026, SHA-256 do documento
``452e879741752189b5ce16618329c0ffd3b741f78f0f2c15b6eded6b08f33f61``). Este módulo só transcreve
o schema e as regras de rejeição delas. A 4.1 mantém ``version = "1"`` e acrescenta dois campos
normativos (entram no payload e no hash): ``revision = "4.1"`` e ``snapshot_date_basis_order``.
Um contrato gravado sem ``revision`` é da rev. 4 e é recusado com esse motivo: precisa ser
recriado pendente e reaprovado (nunca é convertido em silêncio).

Mesmo padrão de ``class_budget.py``: dataclass imutável, ``validate`` que levanta
``ValueError`` com o motivo, ``content_hash`` de 16 hex sobre o payload canônico (sem a
origem), leitura estrita (chave desconhecida é erro, nunca cai em silêncio para um padrão).

Aprovar este contrato autoriza **gerar** propostas, nada além: ``automatic_action`` é travado
em ``"nenhuma"`` e ``trigger`` em ``"manual_command"``. Nenhuma aprovação aqui autoriza ordem,
rebalanceamento ou movimentação financeira.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from iip.knowledge.models import Verdict

CONTRACT_RELATIVE_PATH = Path("02_Portfolio") / "Aporte_Contrato.json"
CONTRACT_TYPE = "aporte_proposto_contract"
CONTRACT_VERSION = "1"
CONTRACT_REVISION = "4.1"
# Rev. 4.1 §4: lista única -- vocabulário permitido E ordem de precedência das bases da
# snapshot_date. A precedência é garantia do procedimento de captura/conversão; o motor só valida
# que a base registrada pertence a esta lista e que as regras dela foram cumpridas.
SNAPSHOT_DATE_BASIS_ORDER = (
    "source_declared_date",
    "source_reference_date",
    "capture_date",
)
APPROVAL_STATUSES = ("pendente", "aprovada")
AUTOMATIC_ACTION = "nenhuma"

# A v1 fixa o universo de vereditos (decisão do usuário, 26/09/2026): AUMENTAR não é elegível;
# distinguir AUMENTAR exige uma revisão do contrato. O vocabulário é o gravado na nota DEC-*
# (``iip.knowledge.models.Verdict``); VENDER é do motor e não aparece aqui.
V1_ELIGIBLE = ("COMPRAR", "MANTER")
V1_VETOED = ("AGUARDAR", "REDUZIR", "ENCERRAR", "AUMENTAR")
ENGINE_ONLY_VERDICTS = ("VENDER",)

# Campos de enumeração da v1: cada um tem um único valor aceito. Qualquer outro valor é "enum
# desconhecido" (§14) -- mudar um deles é mudar o contrato, não configurar.
_FIXED_FIELDS: dict[str, str] = {
    "verdict_vocabulary": "knowledge",
    "score_formula": "decision_score * (0.75 + 0.25 * gap)",
    "distribution": "greedy_by_rank",
    "class_source": "target_policy",
    "class_limit": "class_target",
    "asset_limit": "individual_target",
    "decision_score_persistence": "required",
    "decision_universe": "policy_active_asset_lines",
    "decision_round": "latest_complete_round_in_cycle",
    "decision_fallback": "none",
    "current_snapshot_date": "front_matter_required",
    "price_source": "refresh_daily_snapshot",
    "validity": "same_month",
    "units": "whole_shares",
    "leftover": "explicit_not_redistributed",
    "cadence": "monthly",
    "trigger": "manual_command",
    "automatic_action": AUTOMATIC_ACTION,
}

_ROOT_KEYS = frozenset(
    {
        "type",
        "version",
        "origin",
        "monthly_budget_brl",
        "eligible_verdicts",
        "vetoed_verdicts",
        "intrinsic_weight",
        "gap_weight",
        "income_component",
        "monthly_asset_cap_pct",
        "approval_status",
        "decided_on",
        "revision",
        "snapshot_date_basis_order",
        *_FIXED_FIELDS,
    }
)

_WEIGHT_SUM_TOLERANCE = 1e-9


@dataclass(frozen=True)
class AporteContract:
    version: str = CONTRACT_VERSION
    revision: str = CONTRACT_REVISION
    snapshot_date_basis_order: tuple[str, ...] = SNAPSHOT_DATE_BASIS_ORDER
    origin: str = ""
    monthly_budget_brl: float = 1350.0
    eligible_verdicts: tuple[str, ...] = V1_ELIGIBLE
    vetoed_verdicts: tuple[str, ...] = V1_VETOED
    intrinsic_weight: float = 0.75
    gap_weight: float = 0.25
    income_component: bool = False
    monthly_asset_cap_pct: float = 25.0
    approval_status: str = "pendente"
    decided_on: str | None = None
    verdict_vocabulary: str = _FIXED_FIELDS["verdict_vocabulary"]
    score_formula: str = _FIXED_FIELDS["score_formula"]
    distribution: str = _FIXED_FIELDS["distribution"]
    class_source: str = _FIXED_FIELDS["class_source"]
    class_limit: str = _FIXED_FIELDS["class_limit"]
    asset_limit: str = _FIXED_FIELDS["asset_limit"]
    decision_score_persistence: str = _FIXED_FIELDS["decision_score_persistence"]
    decision_universe: str = _FIXED_FIELDS["decision_universe"]
    decision_round: str = _FIXED_FIELDS["decision_round"]
    decision_fallback: str = _FIXED_FIELDS["decision_fallback"]
    current_snapshot_date: str = _FIXED_FIELDS["current_snapshot_date"]
    price_source: str = _FIXED_FIELDS["price_source"]
    validity: str = _FIXED_FIELDS["validity"]
    units: str = _FIXED_FIELDS["units"]
    leftover: str = _FIXED_FIELDS["leftover"]
    cadence: str = _FIXED_FIELDS["cadence"]
    trigger: str = _FIXED_FIELDS["trigger"]
    automatic_action: str = AUTOMATIC_ACTION

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(_payload(self, with_origin=False), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    @property
    def monthly_asset_cap_brl(self) -> float:
        return self.monthly_asset_cap_pct / 100 * self.monthly_budget_brl


# --- validação (§14) -----------------------------------------------------------------------


def _is_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int | float)
        and math.isfinite(value)
    )


def validate(
    contract: AporteContract,
) -> None:  # noqa: C901 - uma checagem por regra do §14
    """Levanta ``ValueError`` com o motivo se o contrato deve ser rejeitado (§14)."""
    if contract.version != CONTRACT_VERSION:
        raise ValueError(f"version {contract.version!r}, esperado {CONTRACT_VERSION!r}")
    if contract.revision != CONTRACT_REVISION:
        raise ValueError(
            f"revision {contract.revision!r}, esperado {CONTRACT_REVISION!r}"
        )
    order = contract.snapshot_date_basis_order
    if tuple(order) != SNAPSHOT_DATE_BASIS_ORDER:
        raise ValueError(
            f"snapshot_date_basis_order={list(order)!r}; a rev. 4.1 fixa "
            f"{list(SNAPSHOT_DATE_BASIS_ORDER)!r} (vocabulário e ordem)"
        )
    if not _is_number(contract.monthly_budget_brl) or contract.monthly_budget_brl <= 0:
        raise ValueError(
            f"monthly_budget_brl={contract.monthly_budget_brl!r} precisa ser > 0"
        )
    for name in ("intrinsic_weight", "gap_weight"):
        value = getattr(contract, name)
        if not _is_number(value) or not 0 <= value <= 1:
            raise ValueError(f"{name}={value!r} fora de [0, 1]")
    if abs(contract.intrinsic_weight + contract.gap_weight - 1) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError("intrinsic_weight + gap_weight precisa somar 1")
    if contract.income_component is not False:
        raise ValueError("income_component precisa ser false na v1")
    cap = contract.monthly_asset_cap_pct
    if not _is_number(cap) or not 0 < cap <= 100:
        raise ValueError(f"monthly_asset_cap_pct={cap!r} fora de (0, 100]")
    for name in ("eligible_verdicts", "vetoed_verdicts"):
        values = getattr(contract, name)
        if len(set(values)) != len(values):
            raise ValueError(f"{name} tem veredito repetido")
    eligible, vetoed = set(contract.eligible_verdicts), set(contract.vetoed_verdicts)
    engine_only = (eligible | vetoed) & set(ENGINE_ONLY_VERDICTS)
    if engine_only:
        raise ValueError(
            f"veredito do vocabulário do motor nas listas: {sorted(engine_only)} "
            "(use o vocabulário da nota: ENCERRAR)"
        )
    known = {v.value for v in Verdict}
    unknown = (eligible | vetoed) - known
    if unknown:
        raise ValueError(f"veredito desconhecido: {sorted(unknown)}")
    if eligible & vetoed:
        raise ValueError(
            f"veredito elegível e vetado ao mesmo tempo: {sorted(eligible & vetoed)}"
        )
    uncovered = known - eligible - vetoed
    if uncovered:
        raise ValueError(f"veredito fora de eligible e de vetoed: {sorted(uncovered)}")
    if eligible != set(V1_ELIGIBLE) or vetoed != set(V1_VETOED):
        raise ValueError(
            f"a v1 fixa eligible={list(V1_ELIGIBLE)} e vetoed={list(V1_VETOED)}; "
            "mudar isso exige revisão do contrato"
        )
    for name, expected in _FIXED_FIELDS.items():
        value = getattr(contract, name)
        if value != expected:
            raise ValueError(
                f"{name}={value!r} (enum desconhecido; a v1 aceita {expected!r})"
            )
    if contract.approval_status not in APPROVAL_STATUSES:
        raise ValueError(
            f"approval_status {contract.approval_status!r} "
            f"(use {' ou '.join(APPROVAL_STATUSES)})"
        )
    if contract.decided_on is not None:
        try:
            _dt.date.fromisoformat(contract.decided_on)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"decided_on {contract.decided_on!r} não é AAAA-MM-DD"
            ) from exc
    if contract.approval_status == "aprovada" and not contract.decided_on:
        raise ValueError("contrato aprovado exige a data da decisão (decided_on)")


# --- serialização --------------------------------------------------------------------------


def _payload(contract: AporteContract, *, with_origin: bool = True) -> dict:
    payload = {
        "type": CONTRACT_TYPE,
        "version": contract.version,
        "revision": contract.revision,
        "snapshot_date_basis_order": list(contract.snapshot_date_basis_order),
        "monthly_budget_brl": contract.monthly_budget_brl,
        "eligible_verdicts": list(contract.eligible_verdicts),
        "vetoed_verdicts": list(contract.vetoed_verdicts),
        "intrinsic_weight": contract.intrinsic_weight,
        "gap_weight": contract.gap_weight,
        "income_component": contract.income_component,
        "monthly_asset_cap_pct": contract.monthly_asset_cap_pct,
        "approval_status": contract.approval_status,
        "decided_on": contract.decided_on,
        **{name: getattr(contract, name) for name in _FIXED_FIELDS},
    }
    if with_origin:
        payload["origin"] = contract.origin
    return payload


def save_contract(vault_path: str | Path, contract: AporteContract) -> Path:
    validate(contract)
    path = Path(vault_path) / CONTRACT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_payload(contract), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def load_contract(vault_path: str | Path) -> AporteContract | None:
    """O contrato gravado, ou ``None`` se não há arquivo. Um arquivo que existe mas está errado
    levanta ``ValueError`` com o motivo: nunca cai em silêncio para um padrão."""
    path = Path(vault_path) / CONTRACT_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: não é um JSON válido ({exc})") from exc
    try:
        if not isinstance(raw, dict):
            raise ValueError("a raiz precisa ser um objeto")
        if "revision" not in raw:
            raise ValueError(
                "contrato sem 'revision': é da rev. 4, e o código exige a rev. "
                f"{CONTRACT_REVISION}. Ele precisa ser recriado pendente e reaprovado; "
                "nada é convertido automaticamente"
            )
        unknown = set(raw) - _ROOT_KEYS
        if unknown:
            raise ValueError(f"chave desconhecida na raiz {sorted(unknown)}")
        missing = _ROOT_KEYS - {"origin", "decided_on"} - set(raw)
        if missing:
            raise ValueError(f"faltam chaves: {sorted(missing)}")
        if raw["type"] != CONTRACT_TYPE:
            raise ValueError(f"type {raw['type']!r}, esperado {CONTRACT_TYPE!r}")
        for name in (
            "eligible_verdicts",
            "vetoed_verdicts",
            "snapshot_date_basis_order",
        ):
            if not isinstance(raw[name], list) or not all(
                isinstance(v, str) for v in raw[name]
            ):
                raise ValueError(f"{name} precisa ser uma lista de textos")
        contract = AporteContract(
            version=raw["version"],
            revision=raw["revision"],
            snapshot_date_basis_order=tuple(raw["snapshot_date_basis_order"]),
            origin=str(raw.get("origin", "")),
            monthly_budget_brl=raw["monthly_budget_brl"],
            eligible_verdicts=tuple(raw["eligible_verdicts"]),
            vetoed_verdicts=tuple(raw["vetoed_verdicts"]),
            intrinsic_weight=raw["intrinsic_weight"],
            gap_weight=raw["gap_weight"],
            income_component=raw["income_component"],
            monthly_asset_cap_pct=raw["monthly_asset_cap_pct"],
            approval_status=raw["approval_status"],
            decided_on=raw.get("decided_on"),
            **{name: raw[name] for name in _FIXED_FIELDS},
        )
        validate(contract)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{path}: contrato mal formado ({exc!r})") from exc
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return contract


def build_contract(
    *, origin: str = "criado pendente a partir da rev. 4.1 aprovada"
) -> AporteContract:
    """O contrato v1 com os valores da rev. 4.1, sempre ``pendente``: a aprovação é do usuário,
    gravada por ele no arquivo (mesmo protocolo da política e do orçamento por classe).
    """
    contract = AporteContract(origin=origin)
    validate(contract)
    return contract
