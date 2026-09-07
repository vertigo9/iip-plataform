"""Stable data contracts between IIP layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetSnapshot:
    ticker: str
    asset_class: str
    segment: str | None
    manager: str | None
    risk_profile: str | None
    as_of: str


@dataclass(frozen=True)
class DecisionSnapshot:
    ticker: str
    action: str
    score: float
    confidence: float
    evidence_ids: tuple[str, ...]
    model_version: str
