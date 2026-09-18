"""B3's own official historical quotes file (COTAHIST) -- the real
source for exchange-traded price history (acoes, ETFs, FIIs, BDRs),
as opposed to CVM, which regulates/collects fund administration data
but does not publish market price series itself.

One fixed-width .TXT file per year inside a .ZIP, free, no API key,
covering every instrument traded on B3's "mercado a vista" (spot
market) that day. Confirmed live (17/09/2026) against
COTAHIST_A2026.ZIP: 2,847,953 lines, type "01" quote records validated
field-by-field against a known real row (LEVE3, 02/01/2026) and
cross-checked for BBSE3's closing price against bolsai's live quote.

Layout (fixed-width, 1-indexed positions per B3's own published
layout, "REGISTRO TIPO 01 - COTACOES"): TIPREG(1-2) DATA_PREGAO(3-10)
CODBDI(11-12) CODNEG(13-24) TPMERC(25-27) NOMRES(28-39) ESPECI(40-49)
PRAZOT(50-52) MODREF(53-56) PREABE(57-69) PREMAX(70-82) PREMIN(83-95)
PREMED(96-108) PREULT(109-121) PREOFC(122-134) PREOFV(135-147)
TOTNEG(148-152) QUATOT(153-170) VOLTOT(171-188) ... Price fields carry
an implied 2 decimals (e.g. "0000000003350" == 33.50).

Only TPMERC "010" (mercado a vista / spot) rows are parsed -- forward
and options series for the same ticker use other TPMERC codes and are
not price history for the underlying.

Known real gap, found live (17/09/2026): LFTB11 (an RCVM 175 "FIIM"
fund with a real ~R$5.8bi CVM-registered patrimonio) does not appear
anywhere in this file at all, nor in any other B3/CVM dataset checked
this session -- its own B3 page shows blank 6-month trade count/volume
averages, consistent with genuinely thin or absent secondary-market
trading rather than a parsing gap. Do not assume every listed ticker
has COTAHIST coverage; check, don't guess.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist"
_SPOT_MARKET = "010"
_RECORD_LENGTH = 245


@dataclass(frozen=True)
class CotahistTarget:
    year: int
    url: str


@dataclass(frozen=True)
class CotahistQuote:
    ticker: str
    date: str  # ISO YYYY-MM-DD
    open: float
    high: float
    low: float
    avg: float
    close: float
    trades: int
    volume: float


def build_target(year: int) -> CotahistTarget:
    if year < 1986:
        raise ValueError("B3 COTAHIST annual files start in 1986")
    return CotahistTarget(year=year, url=f"{BASE_URL}/COTAHIST_A{year}.ZIP")


def _price(raw: str) -> float:
    return int(raw) / 100.0


def parse_cotahist_lines(
    lines: list[str], *, tickers: frozenset[str] | None = None
) -> tuple[CotahistQuote, ...]:
    """Parse type "01" quote records, spot market only.

    ``tickers`` (already uppercased) restricts parsing to those codes
    when given -- the file covers the whole exchange (250k+ distinct
    codes, mostly options/forward series), so callers almost always
    want to filter rather than materialize everything.
    """
    normalized = frozenset(t.upper() for t in tickers) if tickers is not None else None
    quotes: list[CotahistQuote] = []
    for line in lines:
        if len(line) < _RECORD_LENGTH or line[0:2] != "01":
            continue
        if line[24:27] != _SPOT_MARKET:
            continue
        codneg = line[12:24].strip()
        if normalized is not None and codneg not in normalized:
            continue
        date_raw = line[2:10]
        quotes.append(
            CotahistQuote(
                ticker=codneg,
                date=f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}",
                open=_price(line[56:69]),
                high=_price(line[69:82]),
                low=_price(line[82:95]),
                avg=_price(line[95:108]),
                close=_price(line[108:121]),
                trades=int(line[147:152]),
                volume=int(line[170:188]) / 100.0,
            )
        )
    return tuple(quotes)
