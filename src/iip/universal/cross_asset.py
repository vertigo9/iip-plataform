"""Cross-asset portfolio normalization."""

from __future__ import annotations

from dataclasses import dataclass

from .taxonomy import AssetClass


@dataclass(frozen=True)
class CrossAssetSignal:
    ticker: str
    asset_class: AssetClass
    score: float
    income_role: str | None = None
    currency_exposure: str | None = None


def normalize_signal(
    ticker: str,
    asset_class: AssetClass,
    score: float,
    *,
    income_role: str | None = None,
    currency_exposure: str | None = None,
) -> CrossAssetSignal:
    return CrossAssetSignal(
        ticker.upper(),
        asset_class,
        max(0.0, min(10.0, float(score))),
        income_role,
        currency_exposure,
    )
