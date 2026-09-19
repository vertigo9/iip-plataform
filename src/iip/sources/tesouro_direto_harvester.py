"""HTTP transport for the Tesouro Direto rates CSV.

No authentication -- an open-data file. Same injectable-``opener`` pattern
as the other harvesters, so tests never touch the network.

The newest business day is at the top of the file, so a small ranged read is
enough. Confirmed live that the server sometimes honours ``Range`` (206) and
sometimes ignores it and returns the whole ~14.5 MB file (200); both are
handled: a 206 body has its (possibly cut) last line dropped, a 200 body is
used whole. The parser takes the newest date it actually finds, and
``long_ntnb_rate`` rejects a stale one, so an unexpected ordering degrades to
"unavailable" instead of a wrong rate.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime
from urllib.request import Request, urlopen

from .tesouro_direto import (
    DEFAULT_MAX_AGE_DAYS,
    URL,
    NtnbRate,
    long_ntnb_rate,
    parse_rates,
)

_HEAD_BYTES = 300_000  # ~ a month of business days


class TesouroDiretoHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 90.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch_long_ntnb_rate(
        self,
        *,
        today: date | None = None,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> NtnbRate | None:
        request = Request(
            URL,
            headers={
                "User-Agent": self.user_agent,
                "Range": f"bytes=0-{_HEAD_BYTES - 1}",
            },
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status = 200 if raw_status is None else int(raw_status)
        text = response.read().decode("latin-1")
        rows = parse_rates(text, drop_last_line=status == 206)
        return long_ntnb_rate(
            rows, today=today or datetime.now(UTC).date(), max_age_days=max_age_days
        )


_RATE_MEMO: ContextVar[dict | None] = ContextVar("iip_ntnb_rate_memo", default=None)


def long_ntnb_rate_cached() -> NtnbRate | None:
    """The long NTN-B real yield, fetched ONCE per ``shared_ntnb_rate_cache()``
    block (a failure is memoized too, so a batch does not retry a dead network
    once per position). Outside a block it just fetches."""
    memo = _RATE_MEMO.get()
    if memo is not None and "outcome" in memo:
        outcome = memo["outcome"]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    try:
        rate = TesouroDiretoHTTPHarvester().fetch_long_ntnb_rate()
    except Exception as exc:  # noqa: BLE001 -- memoized and re-raised for the caller to handle
        if memo is not None:
            memo["outcome"] = exc
        raise
    if memo is not None:
        memo["outcome"] = rate
    return rate


@contextmanager
def shared_ntnb_rate_cache() -> Iterator[None]:
    token = _RATE_MEMO.set({})
    try:
        yield
    finally:
        _RATE_MEMO.reset(token)
