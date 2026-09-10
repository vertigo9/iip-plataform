"""B3 quotes via brapi.dev (third-party wrapper) — general coverage.

Kept alongside bolsai (``b3_bolsai.py``), not as a replacement: each
covers a real gap the other doesn't, confirmed live, not assumed.
  - bolsai: richer free-tier data per call (200 req/day vs. brapi's 1
    asset/request) and denser FII-specific fields (P/VP, DY, NAV,
    vacancy, delinquency) — but its own published coverage is "350+
    ações" + "400+ FIIs", NO BDR category (confirmed live: a bolsai
    /fundamentals call for AAPL34 returned 404).
  - brapi.dev: narrower free tier, but genuinely covers BDRs too
    (confirmed in brapi's own docs: a ``type=bdr`` filter on the
    quote-list endpoint, and a dedicated blog post with real BDR
    ticker examples — AAPL34, MSFT34, GOGL34, TSLA34, etc.).

The B3 exchange itself still has no free public REST API for
per-ticker quotes (see the original audit note this module carried
before — "B3 for Developers" is paid/licensed; the only free official
channel is the Boletim Diário bulk file, POST, whole day's file, no
per-ticker query). Both bolsai and brapi.dev are third-party
aggregators, not official B3 channels — cross-check important numbers
against another source when it matters.

Uses the legacy path-based endpoint (``/api/quote/{tickers}``), not
brapi's newer ``/api/v2/stocks/quote`` — that v2 route is scoped to
stocks only (a mixed stock+FII query against it returns 400, confirmed
live). The legacy endpoint accepts any B3-listed ticker in the same
comma-separated call — ações, FIIs, ETFs, BDRs alike.

Confirmed live against the free plan: it allows only 1 asset per
request (a 2-ticker call returns 400, ``QUOTES_PER_REQUEST_EXCEEDED``
— paid plans raise this limit). Callers should build one single-symbol
target per ticker and fetch them with
``BrapiHTTPHarvester.fetch_many`` rather than batching symbols into
one ``build_target`` call.

Same request/response split as the other sources: this module builds
the request URL and parses the response; it performs no HTTP request
itself (see ``.b3_brapi_harvester`` for the transport, which also
carries the API token — never embedded in the URL here, so it can't
end up logged or persisted anywhere a URL might be recorded).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

BASE_URL = "https://brapi.dev/api/quote"


@dataclass(frozen=True)
class BrapiTarget:
    symbols: tuple[str, ...]
    url: str


@dataclass(frozen=True)
class BrapiQuote:
    symbol: str
    short_name: str | None
    currency: str | None
    regular_market_price: float | None
    regular_market_change_percent: float | None


def build_target(symbols: tuple[str, ...]) -> BrapiTarget:
    """Build the request URL for one or more B3 tickers (stocks, FIIs,
    ETFs, BDRs — any ticker listed on B3).

    Tickers are joined directly into the URL path, comma-separated —
    this is the endpoint's documented way of batching mixed asset
    types in a single call, though the free plan's 1-asset-per-request
    limit means callers should normally pass one symbol per target.
    """

    if not symbols:
        raise ValueError("symbols must not be empty")

    normalized = tuple(symbol.strip().upper() for symbol in symbols)
    if any(not symbol for symbol in normalized):
        raise ValueError("symbols must not contain empty tickers")

    url = f"{BASE_URL}/{','.join(normalized)}"
    return BrapiTarget(symbols=normalized, url=url)


def parse_quote_response(body: bytes) -> tuple[BrapiQuote, ...]:
    """Parse brapi.dev's ``{"results": [...]}`` quote response."""

    raw = json.loads(body.decode("utf-8"))
    quotes = []
    for item in raw.get("results", []):
        quotes.append(
            BrapiQuote(
                symbol=str(item.get("symbol", "")),
                short_name=item.get("shortName"),
                currency=item.get("currency"),
                regular_market_price=_as_float(item.get("regularMarketPrice")),
                regular_market_change_percent=_as_float(
                    item.get("regularMarketChangePercent")
                ),
            )
        )
    return tuple(quotes)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
