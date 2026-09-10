"""B3 quotes via brapi.dev (third-party wrapper).

Audit finding: the B3 exchange itself has no free public REST API for
per-ticker quotes. "B3 for Developers" is a paid/licensed product; the
only free official channel is the Boletim Diário bulk file
(arquivos.b3.com.br/bdi, POST, whole day's file, no per-ticker query).
Per explicit decision, this module integrates brapi.dev instead — a
third-party aggregator with a free tier, NOT an official B3 channel.
Treat data from this provider as coming from an external intermediary:
cross-check important numbers against another source when it matters,
the same way BACEN and IBGE's IPCA cross-checked against each other.

Uses the legacy path-based endpoint (``/api/quote/{tickers}``), not
brapi's newer ``/api/v2/stocks/quote`` — that v2 route is scoped to
stocks only (a mixed stock+FII query against it returns 400, confirmed
live). The legacy endpoint is explicitly documented as accepting mixed
asset types (ações, FIIs, ETFs, BDRs) in a single comma-separated call,
matching multiple official brapi.dev examples (e.g.
``/api/quote/PETR4,HGLG11,MXRF11``).

Confirmed live against the free plan: it allows only 1 asset per
request (a 2-ticker call returns 400,
``QUOTES_PER_REQUEST_EXCEEDED`` — paid plans raise this limit). Callers
on the free plan should build one single-symbol target per ticker and
fetch them with ``BrapiHTTPHarvester.fetch_many`` rather than batching
symbols into one ``build_target`` call — this module does not enforce
that limit itself, since it varies by plan.

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
    """Build the request URL for one or more B3 tickers (stocks, FIIs, ETFs, BDRs).

    Tickers are joined directly into the URL path, comma-separated —
    this is the endpoint's documented way of batching mixed asset
    types in a single call.
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
