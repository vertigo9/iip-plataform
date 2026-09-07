"""Decision-intelligence models for the IIP."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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


@dataclass(frozen=True)
class Decision:
    ticker: str
    verdict: Verdict
    score: float
    confidence: float
    reasons: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...] = ()
