"""Thesis-change signals derived from explicit evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ThesisSignal(StrEnum):
    REFORCO = "Reforço"
    NEUTRO = "Neutro"
    ATENCAO = "Ponto de atenção"
    MUDANCA = "Mudança de tese"


@dataclass(frozen=True)
class ThesisObservation:
    ticker: str
    signal: ThesisSignal
    evidence_ids: tuple[str, ...]
    rationale: str


def observe(
    ticker: str,
    signal: ThesisSignal,
    evidence_ids: tuple[str, ...],
    rationale: str,
) -> ThesisObservation:
    return ThesisObservation(
        ticker=ticker.upper(),
        signal=signal,
        evidence_ids=tuple(dict.fromkeys(evidence_ids)),
        rationale=rationale.strip(),
    )
