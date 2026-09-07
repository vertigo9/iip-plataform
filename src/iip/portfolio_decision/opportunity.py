"""Portfolio opportunity scoring contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    ticker: str
    intrinsic_score: float
    allocation_gap: float
    income_need: float
    final_score: float


def build(
    ticker: str,
    intrinsic_score: float,
    allocation_gap: float,
    income_need: float = 0.0,
) -> Opportunity:
    intrinsic = max(0.0, min(10.0, float(intrinsic_score)))
    gap = max(0.0, min(1.0, float(allocation_gap)))
    income = max(0.0, min(1.0, float(income_need)))

    # Portfolio-decision contract:
    # 75% intrinsic base + 12.5% allocation gap + 12.5% income need.
    # Example required by the existing tests:
    # 9 * (0.75 + 0.125*0.5 + 0.125*0.5) = 7.875
    final = intrinsic * (0.75 + 0.125 * gap + 0.125 * income)

    return Opportunity(
        ticker=ticker.upper(),
        intrinsic_score=intrinsic,
        allocation_gap=gap,
        income_need=income,
        final_score=round(final, 12),
    )


def rank(
    opportunities: tuple[Opportunity, ...],
) -> tuple[Opportunity, ...]:
    return tuple(
        sorted(
            opportunities,
            key=lambda item: (-item.final_score, item.ticker),
        )
    )
