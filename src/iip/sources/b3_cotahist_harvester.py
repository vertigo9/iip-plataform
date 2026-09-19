"""HTTP transport for B3 COTAHIST targets -- no API key, no auth
header (unlike bolsai/brapi): this is a public static file download.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .b3_cotahist import CotahistQuote, CotahistTarget, parse_cotahist_lines


@dataclass(frozen=True)
class FetchedCotahist:
    target: CotahistTarget
    status_code: int
    quotes: tuple[CotahistQuote, ...]
    content_hash: str
    final_url: str = ""
    body: bytes = b""


class B3CotahistHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 180.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(
        self, target: CotahistTarget, *, tickers: frozenset[str] | None = None
    ) -> FetchedCotahist:
        """Download one year's annual file (tens of MB) and parse only
        the requested ``tickers`` -- pass explicit tickers whenever
        possible, the file covers the whole exchange."""
        request = Request(
            target.url, headers={"User-Agent": self.user_agent}, method="GET"
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        body = response.read()
        final_url = str(
            response.geturl() if hasattr(response, "geturl") else target.url
        )

        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            name = archive.namelist()[0]
            text = archive.read(name).decode("latin-1")

        lines = text.splitlines()
        quotes = parse_cotahist_lines(lines, tickers=tickers)

        return FetchedCotahist(
            target=target,
            status_code=status_code,
            quotes=quotes,
            content_hash=hashlib.sha256(body).hexdigest(),
            final_url=final_url,
            body=body,
        )
