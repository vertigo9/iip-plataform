"""Thesis state normalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ThesisState(StrEnum):
    REFORCO = "Reforço"
    NEUTRO = "Neutro"
    ATENCAO = "Ponto de atenção"
    MUDANCA = "Mudança de tese"


@dataclass(frozen=True)
class ThesisStateSnapshot:
    ticker: str
    state: ThesisState
    rationale: str
    evidence_ids: tuple[str, ...] = ()
