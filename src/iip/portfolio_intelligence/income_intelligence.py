"""Income concentration and sustainability helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncomeSource:
    ticker: str
    annual_income: float
    weight: float


@dataclass(frozen=True)
class IncomeConcentration:
    ticker: str
    income_share: float


def income_concentration(
    sources: tuple[IncomeSource, ...],
) -> tuple[IncomeConcentration, ...]:
    total = sum(max(0.0, item.annual_income) for item in sources)
    if total <= 0:
        return tuple(IncomeConcentration(item.ticker.upper(), 0.0) for item in sources)
    return tuple(
        IncomeConcentration(
            item.ticker.upper(),
            round(max(0.0, item.annual_income) / total, 12),
        )
        for item in sorted(sources, key=lambda x: (-x.annual_income, x.ticker))
    )
