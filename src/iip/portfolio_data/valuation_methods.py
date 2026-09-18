"""Which valuation methods fit which asset, and the calculators for those
that are implemented.

Motivation: not every valuation method makes sense for every asset. A
book-value-based formula such as Graham's says little about an asset-light
technology company; a per-share NAV method has no meaning for a listed
equity. Running an inapplicable method and reporting its number would be a
fabricated signal, so the choice of methods is decided here, explicitly and
with a stated reason, BEFORE any number is computed -- and every method that
does not produce a value says why (``MethodAttempt.status`` / ``reason``).

Two separate questions, deliberately kept apart:

  - is the method APPROPRIATE for this asset (asset class, then sector /
    industry exclusions)? -- ``applicability``
  - can it be COMPUTED from the data we have (a calculator exists and its
    inputs are present and valid)? -- ``evaluate_valuations``

Only Graham has a calculator today. The catalog already lists the other
methods that are appropriate per class, so they show up as
``not_implemented`` instead of silently vanishing; adding a calculator, or
refining the sector rules, is a change to the tables below and nothing else.

Graham's fair value is ``sqrt(22.5 * LPA * VPA)`` (LPA = earnings per share,
VPA = book value per share). It needs both to be positive -- the square root
of a negative product is undefined, and a company with negative earnings or
book value has no Graham value, not a zero one.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from .valuation import ValuationMethod, ValuationSnapshot, build_snapshot

GRAHAM_MULTIPLIER = 22.5

# Methods appropriate per asset class, in order of preference. Classes with no
# entry (etf, fixed_income, ...) have no method catalogued yet -- reported as
# such, not guessed.
METHODS_BY_ASSET_CLASS: dict[str, tuple[ValuationMethod, ...]] = {
    "equity": (
        ValuationMethod.GRAHAM,
        ValuationMethod.BAZIN,
        ValuationMethod.DCF,
        ValuationMethod.RELATIVE,
    ),
    "fii": (ValuationMethod.NAV, ValuationMethod.YIELD),
}

# Per-method sector/industry exclusions: lowercase substrings matched against
# the asset's sector and industry, with the reason reported when one hits.
SECTOR_EXCLUSIONS: dict[ValuationMethod, tuple[tuple[str, str], ...]] = {
    ValuationMethod.GRAHAM: (
        (
            "tecnologia",
            "Graham parte do valor patrimonial, que não representa empresas "
            "de tecnologia (ativos majoritariamente intangíveis)",
        ),
    ),
}

AttemptStatus = Literal["ok", "not_applicable", "not_implemented", "insufficient_data"]


@dataclass(frozen=True)
class Applicability:
    applicable: bool
    reason: str


@dataclass(frozen=True)
class MethodAttempt:
    method: ValuationMethod
    status: AttemptStatus
    reason: str
    snapshot: ValuationSnapshot | None = None


def applicability(
    method: ValuationMethod,
    asset_class: str,
    sector: str = "",
    industry: str = "",
) -> Applicability:
    methods = METHODS_BY_ASSET_CLASS.get(asset_class.strip().lower())
    if methods is None:
        return Applicability(
            False, f"nenhum método de valuation catalogado para a classe {asset_class!r}"
        )
    if method not in methods:
        return Applicability(
            False, f"{method.value} não se aplica à classe {asset_class!r}"
        )
    haystack = f"{sector} {industry}".lower()
    for needle, reason in SECTOR_EXCLUSIONS.get(method, ()):
        if needle in haystack:
            return Applicability(False, reason)
    return Applicability(True, "aplicável")


def graham_fair_value(lpa: float | None, vpa: float | None) -> float | None:
    """``sqrt(22.5 * LPA * VPA)`` rounded to cents, or ``None`` unless both
    inputs are present and strictly positive."""
    if lpa is None or vpa is None or lpa <= 0 or vpa <= 0:
        return None
    return round(math.sqrt(GRAHAM_MULTIPLIER * lpa * vpa), 2)


def _graham(inputs: Mapping[str, float | None]) -> tuple[float | None, str]:
    lpa = inputs.get("lpa")
    vpa = inputs.get("vpa")
    fair_value = graham_fair_value(lpa, vpa)
    if fair_value is not None:
        return fair_value, f"LPA={lpa}, VPA={vpa}"
    if lpa is None or vpa is None:
        return None, "LPA e VPA são necessários e não estão disponíveis"
    return None, (
        f"LPA={lpa} e VPA={vpa}: Graham exige ambos positivos "
        "(prejuízo ou patrimônio negativo não têm valor justo de Graham)"
    )


# method -> calculator returning (fair_value or None, detail/reason)
CALCULATORS: dict[
    ValuationMethod, Callable[[Mapping[str, float | None]], tuple[float | None, str]]
] = {
    ValuationMethod.GRAHAM: _graham,
}


def evaluate_valuations(
    *,
    ticker: str,
    asset_class: str,
    sector: str = "",
    industry: str = "",
    price: float | None,
    inputs: Mapping[str, float | None],
) -> tuple[MethodAttempt, ...]:
    """Try every method catalogued for the asset's class, in order, and say
    what happened to each. Never raises for missing data and never returns a
    fair value it did not compute from ``inputs``."""

    methods = METHODS_BY_ASSET_CLASS.get(asset_class.strip().lower(), ())
    if not methods:
        return (
            MethodAttempt(
                ValuationMethod.RELATIVE,
                "not_applicable",
                applicability(ValuationMethod.RELATIVE, asset_class).reason,
            ),
        )

    attempts: list[MethodAttempt] = []
    for method in methods:
        fit = applicability(method, asset_class, sector, industry)
        if not fit.applicable:
            attempts.append(MethodAttempt(method, "not_applicable", fit.reason))
            continue
        calculator = CALCULATORS.get(method)
        if calculator is None:
            attempts.append(
                MethodAttempt(method, "not_implemented", "sem calculador implementado")
            )
            continue
        fair_value, detail = calculator(inputs)
        if fair_value is None:
            attempts.append(MethodAttempt(method, "insufficient_data", detail))
            continue
        attempts.append(
            MethodAttempt(
                method,
                "ok",
                detail,
                build_snapshot(ticker, method, fair_value, price),
            )
        )
    return tuple(attempts)


def first_valuation(attempts: tuple[MethodAttempt, ...]) -> ValuationSnapshot | None:
    """The snapshot of the first method (in catalog order) that produced one."""
    return next((a.snapshot for a in attempts if a.snapshot is not None), None)
