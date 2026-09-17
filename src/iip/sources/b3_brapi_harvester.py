"""HTTP transport for brapi.dev quote targets.

Requires an API token (brapi.dev free tier — get one at
https://brapi.dev/dashboard) passed at construction, sent only via the
``Authorization`` header, never embedded in the target URL.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .b3_brapi import BrapiQuote, BrapiTarget, parse_quote_response


@dataclass(frozen=True)
class FetchedQuotes:
    target: BrapiTarget
    status_code: int
    quotes: tuple[BrapiQuote, ...]
    content_type: str = "application/json"
    body: bytes = b""
    final_url: str = ""


class BrapiHTTPHarvester:
    def __init__(
        self,
        token: str,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 20.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        if not token:
            raise ValueError("token must not be empty")
        self._token = token
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: BrapiTarget) -> FetchedQuotes:
        request = Request(
            target.url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        headers = getattr(response, "headers", {})
        content_type = str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        body = response.read()
        quotes = parse_quote_response(body)
        final_url = str(response.geturl() if hasattr(response, "geturl") else target.url)
        return FetchedQuotes(
            target=target,
            status_code=status_code,
            quotes=quotes,
            content_type=content_type or "application/json",
            body=body,
            final_url=final_url,
        )

    def fetch_many(self, targets: tuple[BrapiTarget, ...]) -> tuple[FetchedQuotes, ...]:
        return tuple(self.fetch(target) for target in targets)
