from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class Verdict(str, Enum):
    COMPRAR = "COMPRAR"
    AUMENTAR = "AUMENTAR"
    MANTER = "MANTER"
    AGUARDAR = "AGUARDAR"
    REDUZIR = "REDUZIR"
    ENCERRAR = "ENCERRAR"


class DecisionChange(str, Enum):
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    NO_CHANGE = "NO_CHANGE"
    THESIS_CHANGE = "THESIS_CHANGE"


@dataclass(frozen=True)
class Decision:
    decision_id: str
    ticker: str
    date: date
    new_verdict: Verdict
    previous_verdict: Verdict | None = None
    change_type: DecisionChange = DecisionChange.NO_CHANGE
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    review_triggers: tuple[str, ...] = ()
    thesis_exit_state: str | None = None
    thesis_exit_failed_gates: tuple[str, ...] = ()
    thesis_exit_attention_gates: tuple[str, ...] = ()
    thesis_exit_unknown_gates: tuple[str, ...] = ()
    thesis_exit_critical_failure: bool | None = None


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    ticker: str
    date: date
    source_type: str
    source_url: str | None = None
    title: str | None = None
    document_hash: str | None = None
    relevant_facts: tuple[str, ...] = ()


@dataclass(frozen=True)
class Exposure:
    ticker: str
    factor: str
    weight: float
    confidence: float = 1.0
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Position:
    ticker: str
    asset_class: str
    market_value: float
    weight: float
    target_weight: float | None = None


@dataclass(frozen=True)
class PortfolioSnapshot:
    snapshot_id: str
    created_at: datetime
    portfolio_value: float
    positions: tuple[Position, ...] = field(default_factory=tuple)
