from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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


class Decision(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    decision_id: str
    ticker: str
    date: date
    previous_verdict: Verdict | None = None
    new_verdict: Verdict
    change_type: DecisionChange
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    review_triggers: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    evidence_id: str
    ticker: str
    date: date
    source_type: str
    source_url: str | None = None
    title: str | None = None
    document_hash: str | None = None
    relevant_facts: list[str] = Field(default_factory=list)


class Exposure(BaseModel):
    ticker: str
    factor: str
    weight: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class Position(BaseModel):
    ticker: str
    asset_class: str
    market_value: float
    weight: float
    target_weight: float | None = None


class PortfolioSnapshot(BaseModel):
    snapshot_id: str
    created_at: datetime
    portfolio_value: float
    positions: list[Position]
