"""Universal asset taxonomy for funds and non-fund instruments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AssetClass(StrEnum):
    FUND = "fund"
    EQUITY = "equity"
    ETF = "etf"
    BDR = "bdr"
    ADR = "adr"
    FIXED_INCOME = "fixed_income"
    OTHER = "other"


class FundStructure(StrEnum):
    PAPEL = "Papel"
    TIJOLO = "Tijolo"
    HIBRIDO = "Híbrido"
    FI_INFRA = "FI-Infra"
    FI_AGRO = "FI-Agro"
    HEDGE = "Hedge Fund"
    MULTIMERCADO = "Multimercado"
    OUTROS = "Outros"


@dataclass(frozen=True)
class AssetTaxonomy:
    ticker: str
    asset_class: AssetClass
    structure: str | None = None
    segment: str | None = None
    indexers: tuple[str, ...] = ()
    credit_type: str | None = None
    risk_profile: str | None = None
    manager: str | None = None


def classify_fund(
    ticker: str,
    structure: FundStructure,
    segment: str,
    *,
    indexers: tuple[str, ...] = (),
    credit_type: str | None = None,
    risk_profile: str | None = None,
    manager: str | None = None,
) -> AssetTaxonomy:
    return AssetTaxonomy(
        ticker=ticker.upper(),
        asset_class=AssetClass.FUND,
        structure=structure.value,
        segment=segment.strip(),
        indexers=tuple(dict.fromkeys(indexers)),
        credit_type=credit_type,
        risk_profile=risk_profile,
        manager=manager,
    )


def classify_non_fund(
    ticker: str,
    asset_class: AssetClass,
    *,
    risk_profile: str | None = None,
) -> AssetTaxonomy:
    if asset_class == AssetClass.FUND:
        raise ValueError("use classify_fund for funds")
    return AssetTaxonomy(
        ticker=ticker.upper(),
        asset_class=asset_class,
        risk_profile=risk_profile,
    )
