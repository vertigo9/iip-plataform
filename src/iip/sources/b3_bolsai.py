"""B3 fundamentals + quotes via bolsai (third-party wrapper).

Same audit finding as before: B3 itself has no free public REST API
for per-ticker data. This is a third-party aggregator (bolsai), not an
official B3 channel — same caveat as brapi.dev, which this module
replaces per explicit decision: bolsai's free tier is more generous
(200 requests/day vs. brapi's 1 asset per request) and its response
already includes denser FII-specific data (P/VP, dividend yield, NAV,
vacancy, delinquency) alongside standard equity fundamentals. Cross-check
important numbers against another source when it matters — the same
discipline applied to BACEN/IBGE's IPCA agreement.

Two separate, differently-shaped endpoints — confirmed live and via
bolsai's own docs (https://usebolsai.com/docs), not assumed from
memory:
  - ``GET /api/v1/fundamentals/{ticker}`` — stocks/ETFs/BDRs only.
    Calling it with a FII ticker returns 404 (confirmed live).
  - ``GET /api/v1/fiis/{ticker}`` — FIIs only, a different response
    shape (e.g. ``dividend_yield_ttm`` instead of ``dividend_yield``,
    no P/L since it doesn't apply to funds).
Use ``build_target``/``parse_fundamentals_response`` for stocks and
``build_fii_target``/``parse_fii_response`` for FIIs — do not assume
one endpoint covers both, the same mistake made once already with
brapi.dev's stocks-only v2 route.

Same request/response split as the other sources: this module builds
the request URL and parses the response; it performs no HTTP request
itself (see ``.b3_bolsai_harvester`` for the transport, which carries
the API key — never embedded in the URL here, sent only via the
``X-API-Key`` header).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

BASE_URL = "https://api.usebolsai.com/api/v1"
FUNDAMENTALS_URL = f"{BASE_URL}/fundamentals"
FIIS_URL = f"{BASE_URL}/fiis"


@dataclass(frozen=True)
class BolsaiTarget:
    ticker: str
    url: str
    provider: str = "b3"
    role: str = "market_validation"
    year: int | None = None


@dataclass(frozen=True)
class BolsaiFundamentals:
    ticker: str
    close_price: float | None
    market_cap: float | None
    pl: float | None
    pvp: float | None
    ev_ebitda: float | None
    roe: float | None
    roic: float | None
    net_margin: float | None
    gross_margin: float | None
    dividend_yield: float | None
    net_debt_ebitda: float | None
    lpa: float | None
    vpa: float | None
    ebitda: float | None
    # Total shares (all classes). Absolute count, no scale trap unlike CVM's
    # composição de capital (which mixes thousands and units per company).
    shares_outstanding: float | None = None


@dataclass(frozen=True)
class BolsaiFiiData:
    ticker: str
    name: str | None
    reference_date: str | None
    close_price: float | None
    book_value_per_share: float | None
    pvp: float | None
    dividend_yield_ttm: float | None
    net_asset_value: float | None
    shares_outstanding: float | None
    total_shareholders: float | None
    segment: str | None
    management_type: str | None


def build_target(ticker: str) -> BolsaiTarget:
    """Build the request URL for a B3 **stock** (ação/ETF/BDR) — NOT for
    FIIs, which have their own endpoint. Use ``build_fii_target`` for a
    fundo imobiliário; calling this with a FII ticker returns 404 (the
    ``/fundamentals`` endpoint is stocks-only, confirmed live).
    """

    if not ticker or not ticker.strip():
        raise ValueError("ticker must not be empty")

    normalized = ticker.strip().upper()
    url = f"{FUNDAMENTALS_URL}/{normalized}"
    return BolsaiTarget(ticker=normalized, url=url)


def build_fii_target(ticker: str) -> BolsaiTarget:
    """Build the request URL for a B3 **FII** (fundo imobiliário) —
    NOT for stocks, which use ``build_target``/``/fundamentals``
    instead. Verified against bolsai's own docs
    (https://usebolsai.com/docs): ``GET /api/v1/fiis/{ticker}``.
    """

    if not ticker or not ticker.strip():
        raise ValueError("ticker must not be empty")

    normalized = ticker.strip().upper()
    url = f"{FIIS_URL}/{normalized}"
    return BolsaiTarget(ticker=normalized, url=url)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_fundamentals_response(body: bytes) -> BolsaiFundamentals:
    """Parse bolsai's single-object **stock** fundamentals response
    (``/fundamentals/{ticker}``, not a list)."""

    raw = json.loads(body.decode("utf-8"))
    return BolsaiFundamentals(
        ticker=str(raw.get("ticker", "")),
        close_price=_as_float(raw.get("close_price")),
        market_cap=_as_float(raw.get("market_cap")),
        pl=_as_float(raw.get("pl")),
        pvp=_as_float(raw.get("pvp")),
        ev_ebitda=_as_float(raw.get("ev_ebitda")),
        roe=_as_float(raw.get("roe")),
        roic=_as_float(raw.get("roic")),
        net_margin=_as_float(raw.get("net_margin")),
        gross_margin=_as_float(raw.get("gross_margin")),
        dividend_yield=_as_float(raw.get("dividend_yield")),
        net_debt_ebitda=_as_float(raw.get("net_debt_ebitda")),
        lpa=_as_float(raw.get("lpa")),
        vpa=_as_float(raw.get("vpa")),
        ebitda=_as_float(raw.get("ebitda")),
        shares_outstanding=_as_float(raw.get("shares_outstanding")),
    )


def parse_fii_response(body: bytes) -> BolsaiFiiData:
    """Parse bolsai's single-object **FII** response
    (``/fiis/{ticker}``) — a different shape from the stock endpoint
    (e.g. ``dividend_yield_ttm`` instead of ``dividend_yield``, no P/L
    since it does not apply to FIIs)."""

    raw = json.loads(body.decode("utf-8"))
    return BolsaiFiiData(
        ticker=str(raw.get("ticker", "")),
        name=raw.get("name"),
        reference_date=raw.get("reference_date"),
        close_price=_as_float(raw.get("close_price")),
        book_value_per_share=_as_float(raw.get("book_value_per_share")),
        pvp=_as_float(raw.get("pvp")),
        dividend_yield_ttm=_as_float(raw.get("dividend_yield_ttm")),
        net_asset_value=_as_float(raw.get("net_asset_value")),
        shares_outstanding=_as_float(raw.get("shares_outstanding")),
        total_shareholders=_as_float(raw.get("total_shareholders")),
        segment=raw.get("segment"),
        management_type=raw.get("management_type"),
    )
