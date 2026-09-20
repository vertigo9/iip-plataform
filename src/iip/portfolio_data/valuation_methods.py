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

Graham and Bazin have calculators today. The catalog already lists the other
methods that are appropriate per class, so they show up as
``not_implemented`` instead of silently vanishing; adding a calculator, or
refining the sector rules, is a change to the tables below and nothing else.

Bazin's ceiling price is ``dividend per share / required yield``. Bazin
fixed the required yield at 6% (the risk-free rate of the 1990s). Here it is
the CURRENT REAL yield of the longest NTN-B (``iip.sources.tesouro_direto``),
passed in as ``ntnb_real_yield``: dividends of a company that passes inflation
through behave like a real yield, so the inflation-linked government coupon is
the opportunity cost to beat. When rates rise the ceiling falls (more discount
demanded), when they fall it rises. No rate, no Bazin value -- it never falls
back to a silent 6%.

Two kinds of rule decide how a method is used for an asset, each stated with
its reason:

  - DATA CONDITIONS: a method's own premise must hold in the asset's data.
    Bazin assumes a recurring, sustainable dividend, so it needs a track record
    (``BAZIN_MIN_CONSISTENCY_YEARS`` consecutive paying years) and a payout that
    earnings can support (``BAZIN_MAX_PAYOUT_PCT``). A missing field is not a
    violation (unknown), a present one that fails is.
  - SECTOR ORDER: which method LEADS. In dividend-centric businesses (regulated
    utilities, insurers, banks) the dividend is the product, so Bazin comes
    first; elsewhere Graham does. The lead method is the one the batch persists
    and, later, the one that can feed a decision.

FIIs (and FIAGROs, which bolsai serves from the same endpoint) have two methods. NAV: the fund's net asset value per share is the anchor
(``nav_per_share``; P/VP below 1 is a margin of safety). Yield: the SAME income
capitalization as Bazin, over the NTN-B real yield PLUS a FII risk premium
(``FII_YIELD_RISK_PREMIUM``) -- which is only meaningful where distributions
follow inflation --
"Tijolo" funds, whose leases are indexed. "Papel" funds pay CDI/credit-spread
income and "Multiestratégia" funds mix both, so the real-yield comparison would
overstate their ceiling and Yield is not applicable to them. The yield used is
the 12-month trailing one, computed on the fund's net asset value per share
(that is the basis provider data uses), so ``dividend_per_share`` is
``dividend_yield_ttm * nav_per_share``; above ``FII_MAX_SUSTAINABLE_YIELD_PCT``
it is treated as not recurring (extraordinary distributions).

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
from .valuation_exceptions import ValuationExceptions

GRAHAM_MULTIPLIER = 22.5

# Look-through valuation of a fund that only carries stocks (see
# ``iip.portfolio_data.look_through``): it needs at least this share of net assets in
# stocks whose margin of safety was actually computed -- 90% is the minimum the FMP-FGTS
# regulation requires in stocks.
LOOK_THROUGH_MIN_COVERAGE = 0.90

# Methods appropriate per asset class, in order of preference. Classes with no
# entry (fixed_income, ...) have no method catalogued yet -- reported as such,
# not guessed.
METHODS_BY_ASSET_CLASS: dict[str, tuple[ValuationMethod, ...]] = {
    "equity": (
        ValuationMethod.GRAHAM,
        ValuationMethod.BAZIN,
        ValuationMethod.DCF,
        ValuationMethod.RELATIVE,
    ),
    "fii": (ValuationMethod.NAV, ValuationMethod.YIELD),
    # FIAGRO trades and reports like a FII (same bolsai record: NAV per share and
    # 12-month yield), so it shares the FII methods and the "papel" rule for Yield.
    "fiagro": (ValuationMethod.NAV, ValuationMethod.YIELD),
    # Listed FI-Infra funds (CDII11, JURO11, CPTI11): NAV only. The cota comes from
    # CVM's Informe Diário (VL_QUOTA), which tracks the market price closely; there
    # is no income input for Yield and these are "papel" (CDI/credit-spread income).
    # Not the whole fixed_income class: AXIA3 is a FMP-FGTS with no market ticker.
    "fi_infra": (ValuationMethod.NAV,),
    # ETFs (só o LFTB11 na carteira): NAV apenas. A cota patrimonial vem da página
    # oficial da gestora (iip.sources.investo_etf), já que o Informe Diário da CVM não
    # traz o fundo. O preço acompanha o NAV por criação e resgate de cotas, então a
    # "margem" aqui é o prêmio/desconto sobre o NAV, não um sinal de preço errado; e
    # não há método de renda (o LFTB11 acumula, não distribui).
    "etf": (ValuationMethod.NAV,),
    # FMP-FGTS (AXIA3): a fund with no market price, valued through what it holds. The
    # NAV is the reference and the fair value moves it by the weighted margin of safety
    # of the underlying stock(s), which the equity catalog computes.
    "fmp_fgts": (ValuationMethod.LOOK_THROUGH,),
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
    ValuationMethod.YIELD: (
        (
            "papel",
            "renda de FII de papel segue CDI/spreads de crédito (nominal): "
            "compará-la à NTN-B real superestimaria o teto — o NAV é a âncora",
        ),
        (
            "multiestratégia",
            "renda de FII multiestratégia mistura indexadores — não dá para "
            "tratá-la como renda real; o NAV é a âncora",
        ),
    ),
}

# Businesses whose value is mostly their dividend stream: Bazin leads the order.
# Lowercase substrings matched against sector + industry.
DIVIDEND_LED_KEYWORDS: tuple[str, ...] = (
    "utilidade pública",
    "energia elétrica",
    "previdência",
    "seguros",
    "bancos",
    "intermediários financeiros",
)

BAZIN_MIN_CONSISTENCY_YEARS = 3
BAZIN_MAX_PAYOUT_PCT = 100.0

# A trailing FII yield above this is not a recurring income stream (special
# distributions / amortizations), so it must not be capitalized.
FII_MAX_SUSTAINABLE_YIELD_PCT = 20.0

# What a FII must yield ABOVE the real NTN-B (vacancy, liquidity and management
# risk that the government bond does not carry), as a fraction (0.03 = 3.0 p.p.).
# Without it the ceiling compares a FII's yield -- which already embeds that
# premium -- with the risk-free rate alone, and every tijolo fund comes out
# 16%-174% above its price. Measured on 18/09/2026: the median trailing yield of
# the 10 tijolo FIIs in the portfolio was 10.98%, i.e. 3.7 p.p. over the real
# NTN-B (7.30%); 3.0 sits slightly below that market-implied spread, so a fund
# yielding the median is valued a little above its price rather than exactly at it.
# A calibration choice, not a measurement: change it here.
FII_YIELD_RISK_PREMIUM = 0.03

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
    *,
    ticker: str = "",
    exceptions: ValuationExceptions | None = None,
) -> Applicability:
    methods = METHODS_BY_ASSET_CLASS.get(asset_class.strip().lower())
    if methods is None:
        return Applicability(
            False,
            f"nenhum método de valuation catalogado para a classe {asset_class!r}",
        )
    if method not in methods:
        return Applicability(
            False, f"{method.value} não se aplica à classe {asset_class!r}"
        )
    # uma exceção metodológica DECLARADA prevalece sobre as palavras-chave do setor
    if exceptions is not None and ticker:
        declared = exceptions.exclusion(ticker, method.value)
        if declared is not None:
            return Applicability(False, declared.citation())
    haystack = f"{sector} {industry}".lower()
    for needle, reason in SECTOR_EXCLUSIONS.get(method, ()):
        if needle in haystack:
            return Applicability(False, reason)
    return Applicability(True, "aplicável")


def ordered_methods(
    asset_class: str,
    sector: str = "",
    industry: str = "",
    *,
    ticker: str = "",
    exceptions: ValuationExceptions | None = None,
) -> tuple[ValuationMethod, ...]:
    """The class's catalogued methods, Bazin first for dividend-led sectors
    (relative order of the others is kept). A declared methodological exception
    that names a leading method for the ticker puts it first, whatever the sector
    would say."""
    methods = METHODS_BY_ASSET_CLASS.get(asset_class.strip().lower(), ())
    if exceptions is not None and ticker:
        leader = exceptions.leader(ticker)
        if leader is not None:
            chosen = next((m for m in methods if m.value == leader.method), None)
            if chosen is not None:
                return (chosen, *(m for m in methods if m is not chosen))
    haystack = f"{sector} {industry}".lower()
    if ValuationMethod.BAZIN in methods and any(
        k in haystack for k in DIVIDEND_LED_KEYWORDS
    ):
        return (
            ValuationMethod.BAZIN,
            *(m for m in methods if m is not ValuationMethod.BAZIN),
        )
    return methods


def data_condition_violation(
    method: ValuationMethod, inputs: Mapping[str, float | None]
) -> str | None:
    """Why the asset's OWN data breaks the method's premise, or ``None``.
    Absent fields are unknown, not violations."""
    if method is ValuationMethod.YIELD:
        dy = inputs.get("dividend_yield_ttm")
        if dy is not None and dy > FII_MAX_SUSTAINABLE_YIELD_PCT:
            return (
                f"yield de {dy:.1f}% nos últimos 12 meses (acima de "
                f"{FII_MAX_SUSTAINABLE_YIELD_PCT:.0f}%): provável distribuição "
                "extraordinária, não renda recorrente para capitalizar"
            )
    if method is ValuationMethod.BAZIN:
        years = inputs.get("dividend_consistency_years")
        if years is not None and years < BAZIN_MIN_CONSISTENCY_YEARS:
            return (
                f"Bazin exige dividendos recorrentes: {years:g} ano(s) consecutivo(s) "
                f"de pagamento, mínimo {BAZIN_MIN_CONSISTENCY_YEARS} "
                "(0 também pode indicar histórico não obtido)"
            )
        payout = inputs.get("payout_ratio")
        if payout is not None and payout > BAZIN_MAX_PAYOUT_PCT:
            return (
                f"payout de {payout:.0f}% acima de {BAZIN_MAX_PAYOUT_PCT:.0f}%: o "
                "dividendo pago não é sustentado pelo lucro, o teto sairia inflado"
            )
    return None


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


def bazin_ceiling_price(
    dividend_per_share: float | None, required_yield: float | None
) -> float | None:
    """``DPS / required yield`` rounded to cents; ``None`` unless the dividend
    and the yield are both present and strictly positive."""
    if (
        dividend_per_share is None
        or required_yield is None
        or dividend_per_share <= 0
        or required_yield <= 0
    ):
        return None
    return round(dividend_per_share / required_yield, 2)


def _bazin(inputs: Mapping[str, float | None]) -> tuple[float | None, str]:
    dps = inputs.get("dividend_per_share")
    rate = inputs.get("ntnb_real_yield")
    if rate is None or rate <= 0:
        return None, "taxa real da NTN-B longa indisponível (Bazin não usa taxa fixa)"
    if dps is None:
        return None, "dividendo por ação indisponível"
    if dps <= 0:
        return (
            None,
            f"dividendo por ação={dps}: sem dividendos pagos, Bazin não se aplica",
        )
    ceiling = bazin_ceiling_price(dps, rate)
    return ceiling, f"DPS={dps}, taxa real NTN-B={rate:.2%}"


def _nav(inputs: Mapping[str, float | None]) -> tuple[float | None, str]:
    nav = inputs.get("nav_per_share")
    if nav is None:
        return None, "patrimônio por cota (VP/cota) indisponível"
    if nav <= 0:
        return None, f"VP/cota={nav}: patrimônio por cota não positivo"
    return round(nav, 2), f"VP/cota={nav:.2f}"


def _look_through(inputs: Mapping[str, float | None]) -> tuple[float | None, str]:
    nav = inputs.get("nav_per_share")
    margin = inputs.get("look_through_margin")
    coverage = inputs.get("look_through_coverage")
    if nav is None or nav <= 0:
        return None, "cota patrimonial indisponível"
    if margin is None or coverage is None:
        return None, (
            "a margem de segurança da ação subjacente não pôde ser calculada "
            "(sem método aplicável ao subjacente, ou sem dado)"
        )
    if coverage < LOOK_THROUGH_MIN_COVERAGE:
        return None, (
            f"só {coverage:.0%} do patrimônio está em ações avaliadas (mínimo "
            f"{LOOK_THROUGH_MIN_COVERAGE:.0%}): a transparência ficaria incompleta"
        )
    # a fração restante (títulos públicos, caixa, valores a pagar) fica ao NAV: margem zero
    return round(nav * (1.0 + margin), 4), (
        f"cota={nav:.4f} x (1 {margin:+.2%}), margem ponderada das ações que "
        f"cobrem {coverage:.1%} do patrimônio"
    )


def _yield_income(inputs: Mapping[str, float | None]) -> tuple[float | None, str]:
    dps = inputs.get("dividend_per_share")
    rate = inputs.get("ntnb_real_yield")
    if rate is None or rate <= 0:
        return None, "taxa real da NTN-B longa indisponível (sem taxa fixa de reserva)"
    if dps is None:
        return None, "rendimento por cota dos últimos 12 meses indisponível"
    if dps <= 0:
        return None, f"rendimento por cota={dps}: sem distribuição, Yield não se aplica"
    required = rate + FII_YIELD_RISK_PREMIUM
    return bazin_ceiling_price(dps, required), (
        f"renda/cota={dps:.2f}, NTN-B real {rate:.2%} + prêmio {FII_YIELD_RISK_PREMIUM:.2%} "
        f"= {required:.2%}"
    )


# method -> calculator returning (fair_value or None, detail/reason)
CALCULATORS: dict[
    ValuationMethod, Callable[[Mapping[str, float | None]], tuple[float | None, str]]
] = {
    ValuationMethod.GRAHAM: _graham,
    ValuationMethod.BAZIN: _bazin,
    ValuationMethod.NAV: _nav,
    ValuationMethod.YIELD: _yield_income,
    ValuationMethod.LOOK_THROUGH: _look_through,
}


def evaluate_valuations(
    *,
    ticker: str,
    asset_class: str,
    sector: str = "",
    industry: str = "",
    price: float | None,
    inputs: Mapping[str, float | None],
    exceptions: ValuationExceptions | None = None,
) -> tuple[MethodAttempt, ...]:
    """Try every method catalogued for the asset's class, in order, and say
    what happened to each. Never raises for missing data and never returns a
    fair value it did not compute from ``inputs``."""

    methods = ordered_methods(
        asset_class, sector, industry, ticker=ticker, exceptions=exceptions
    )
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
        fit = applicability(
            method, asset_class, sector, industry, ticker=ticker, exceptions=exceptions
        )
        if not fit.applicable:
            attempts.append(MethodAttempt(method, "not_applicable", fit.reason))
            continue
        violation = data_condition_violation(method, inputs)
        if violation is not None:
            attempts.append(MethodAttempt(method, "not_applicable", violation))
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


def has_calculator(asset_class: str) -> bool:
    """Whether any method catalogued for the class can actually be computed."""
    methods = METHODS_BY_ASSET_CLASS.get(asset_class.strip().lower(), ())
    return any(method in CALCULATORS for method in methods)


def first_valuation(attempts: tuple[MethodAttempt, ...]) -> ValuationSnapshot | None:
    """The snapshot of the first method (in catalog order) that produced one."""
    return next((a.snapshot for a in attempts if a.snapshot is not None), None)
