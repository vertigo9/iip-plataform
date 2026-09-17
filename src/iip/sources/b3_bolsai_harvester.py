"""HTTP transport for bolsai targets (stocks and FIIs).

Requires an API key (bolsai free tier — get one at
https://usebolsai.com/dashboard) passed at construction, sent only via
the ``X-API-Key`` header, never embedded in the target URL.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .b3_bolsai import (
    BolsaiFiiData,
    BolsaiFundamentals,
    BolsaiTarget,
    parse_fii_response,
    parse_fundamentals_response,
)


@dataclass(frozen=True)
class FetchedFundamentals:
    target: BolsaiTarget
    status_code: int
    fundamentals: BolsaiFundamentals
    content_type: str = ""
    body: bytes = b""
    final_url: str = ""


@dataclass(frozen=True)
class FetchedFii:
    target: BolsaiTarget
    status_code: int
    fii: BolsaiFiiData
    content_type: str = ""
    body: bytes = b""
    final_url: str = ""


class BolsaiHTTPHarvester:
    def __init__(
        self,
        api_key: str,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 20.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def _request(self, target: BolsaiTarget) -> tuple[int, str, bytes, str]:
        request = Request(
            target.url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "X-API-Key": self._api_key,
            },
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)

        headers = getattr(response, "headers", {})
        content_type = str(
            headers.get("Content-Type", "")
        ).split(";", 1)[0].strip().lower()

        body = response.read()
        final_url = str(
            response.geturl() if hasattr(response, "geturl") else target.url
        )
        return status_code, content_type, body, final_url

    def fetch(self, target: BolsaiTarget) -> FetchedFundamentals:
        """Fetch a **stock** target (built with ``build_target``)."""
        status_code, content_type, body, final_url = self._request(target)
        return FetchedFundamentals(
            target=target,
            status_code=status_code,
            fundamentals=parse_fundamentals_response(body),
            content_type=content_type,
            body=body,
            final_url=final_url,
        )

    def fetch_fii(self, target: BolsaiTarget) -> FetchedFii:
        """Fetch a **FII** target (built with ``build_fii_target``)."""
        status_code, content_type, body, final_url = self._request(target)
        return FetchedFii(
            target=target,
            status_code=status_code,
            fii=parse_fii_response(body),
            content_type=content_type,
            body=body,
            final_url=final_url,
        )

    def fetch_many(
        self, targets: tuple[BolsaiTarget, ...]
    ) -> tuple[FetchedFundamentals, ...]:
        """Batch-fetch several **stock** targets. For FIIs, call
        ``fetch_fii`` per target instead."""
        return tuple(self.fetch(target) for target in targets)

    def fetch_many_fiis(
        self, targets: tuple[BolsaiTarget, ...]
    ) -> tuple[FetchedFii, ...]:
        return tuple(self.fetch_fii(target) for target in targets)
