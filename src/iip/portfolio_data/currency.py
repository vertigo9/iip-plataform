"""Currency exposure normalization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyExposure:
    currency: str
    weight: float


def normalize_currency_weight(currency: str, weight: float) -> CurrencyExposure:
    if not 0 <= weight <= 1:
        raise ValueError("weight must be between 0 and 1")
    return CurrencyExposure(currency.upper(), round(weight, 12))
