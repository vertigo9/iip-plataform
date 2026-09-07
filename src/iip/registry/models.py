"""Universal multi-asset classification contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AssetClass(StrEnum):
    FUND = "fund"
    EQUITY = "equity"
    ETF = "etf"
    BDR = "bdr"
    ADR = "adr"
    FIXED_INCOME = "fixed_income"
    OTHER = "other"


class FundClass(StrEnum):
    FII = "FII"
    FI_INFRA = "FI-Infra"
    FI_AGRO = "FI-Agro"
    OTHER = "Other"


class FundStructure(StrEnum):
    PAPEL = "Papel"
    TIJOLO = "Tijolo"
    HIBRIDO = "Híbrido"
    MULTIESTRATEGIA = "Multiestratégia"
    NAO_APLICAVEL = "N/A"


class RiskLevel(StrEnum):
    BAIXO = "Baixo"
    MEDIO = "Médio"
    ALTO = "Alto"
    NAO_CLASSIFICADO = "Não classificado"


@dataclass(frozen=True)
class FundClassification:
    fund_class: FundClass
    structure: FundStructure
    subtype: str | None = None
    segment: str | None = None
    indexation: tuple[str, ...] = ()
    risk_profile: RiskLevel = RiskLevel.NAO_CLASSIFICADO
    strategy: str | None = None
    investment_scope: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssetClassification:
    asset_class: AssetClass
    subtype: str | None = None
    sector: str | None = None
    segment: str | None = None
    strategy: str | None = None
    fund: FundClassification | None = None


@dataclass(frozen=True)
class AssetIdentity:
    ticker: str
    name: str | None = None
    issuer: str | None = None
    manager: str | None = None
    administrator: str | None = None


@dataclass(frozen=True)
class UniversalAsset:
    identity: AssetIdentity
    classification: AssetClassification
    tags: tuple[str, ...] = field(default_factory=tuple)
