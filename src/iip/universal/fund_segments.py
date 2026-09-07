"""Fund segment conventions for the IIP portfolio."""

from __future__ import annotations

from .taxonomy import FundStructure

FUND_SEGMENT_MAP = {
    "HGRU11": (FundStructure.TIJOLO, "Renda Urbana"),
    "CDII11": (FundStructure.PAPEL, "Infraestrutura"),
    "AFHI11": (FundStructure.PAPEL, "Crédito Imobiliário"),
    "CRAA11": (FundStructure.PAPEL, "Crédito Agrícola"),
    "MANA11": (FundStructure.HEDGE, "Hedge Fund"),
}


def known_segment(ticker: str):
    return FUND_SEGMENT_MAP.get(ticker.upper())
