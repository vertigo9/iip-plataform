"""Decision-intelligence models for the IIP."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .thesis_exit_gate import ThesisExitAssessment


class Verdict(StrEnum):
    COMPRAR = "COMPRAR"
    MANTER = "MANTER"
    AGUARDAR = "AGUARDAR"
    REDUZIR = "REDUZIR"
    VENDER = "VENDER"


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    weight: float = 1.0


@dataclass(frozen=True)
class IntelligenceInput:
    ticker: str
    thesis_signal: str
    risk_level: str
    valuation_score: float
    dividend_score: float
    quality_score: float
    opportunity_score: float
    evidence: tuple[EvidenceRef, ...] = ()
    thesis_exit: ThesisExitAssessment | None = None


@dataclass(frozen=True)
class Decision:
    ticker: str
    verdict: Verdict
    score: float
    confidence: float
    reasons: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...] = ()
    thesis_exit: ThesisExitAssessment | None = None
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SemanticDimension(str, Enum):
    """Dimensão semântica para métricas financeiras (Trace 14/15)."""
    NAV = "NAV"
    MARKET_VALUE = "MARKET_VALUE"


@dataclass(frozen=True)
class MetricObservationIdentity:
    """Contrato canônico de observação de métrica rastreável pelo Atlas."""
    ticker: str
    metric_type: str
    semantic_dimension: SemanticDimension
    value: float
    confidence_score: float
    source_provider: str
    source_url: str
    raw_payload_hash: str
    observed_at: datetime