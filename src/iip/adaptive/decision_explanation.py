"""Structured explanations for portfolio decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Explanation:
    headline: str
    factors: tuple[str, ...]
    evidence_ids: tuple[str, ...]


def build(
    headline: str, factors: tuple[str, ...], evidence_ids: tuple[str, ...]
) -> Explanation:
    return Explanation(
        headline=headline.strip(),
        factors=tuple(
            dict.fromkeys(factor.strip() for factor in factors if factor.strip())
        ),
        evidence_ids=tuple(dict.fromkeys(evidence_ids)),
    )
