"""HTTP transport for bolsai targets (stocks and FIIs).

Requires an API key (bolsai free tier — get one at
https://usebolsai.com/dashboard) passed at construction, sent only via
the ``X-API-Key`` header, never embedded in the target URL.

The free plan is 200 calls a day (``429`` with ``used``/``limit``/``resets`` in
the body once spent), which a batch plus a few re-runs can exhaust. Two
mitigations live here: a legible ``BolsaiRateLimitError`` instead of a bare
"HTTP Error 429", and an OPT-IN on-disk cache of successful responses
(``IIP_BOLSAI_CACHE_DIR`` + ``IIP_BOLSAI_CACHE_TTL_MINUTES``, or the
``cache_dir``/``cache_ttl_seconds`` arguments). The cache stores only ``200``
responses that parse as JSON, keyed by URL (the API key is never written), and
serves an entry only while it is younger than the TTL -- so a price is never
older than the TTL you chose.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
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


class BolsaiRateLimitError(RuntimeError):
    """The bolsai daily quota is spent (HTTP 429)."""


def _rate_limit_message(exc: HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8"))
        return (
            f"bolsai: limite diário do plano gratuito atingido "
            f"({body.get('used')}/{body.get('limit')} chamadas); "
            f"reinicia {body.get('resets', 'no próximo ciclo')}"
        )
    except Exception:  # noqa: BLE001 — the body is only there to enrich the message
        return "bolsai: limite de chamadas atingido (HTTP 429)"


class BolsaiHTTPHarvester:
    def __init__(
        self,
        api_key: str,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 20.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
        cache_dir: Path | None = None,
        cache_ttl_seconds: float = 0.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent
        self._clock = clock
        if cache_dir is None and cache_ttl_seconds == 0.0:
            cache_dir, cache_ttl_seconds = self._cache_from_settings()
        self._cache_dir = (
            Path(cache_dir) if cache_dir and cache_ttl_seconds > 0 else None
        )
        self._cache_ttl = cache_ttl_seconds
        self.cache_hits = 0
        self.cache_misses = 0

    @staticmethod
    def _cache_from_settings() -> tuple[Path | None, float]:
        try:
            from iip.config import get_settings

            settings = get_settings()
            return settings.bolsai_cache_dir, settings.bolsai_cache_ttl_minutes * 60.0
        # settings are optional here; no cache is the safe default
        except Exception:  # noqa: BLE001
            return None, 0.0

    def _cache_path(self, url: str) -> Path | None:
        if self._cache_dir is None:
            return None
        return (
            self._cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"
        )

    def _cache_read(self, url: str) -> bytes | None:
        path = self._cache_path(url)
        if path is None or not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if self._clock() - float(entry["fetched_at"]) > self._cache_ttl:
                return None
            body = entry["body"].encode("utf-8")
            json.loads(body)  # a damaged entry is a miss, never served
            return body
        except Exception:  # noqa: BLE001 — any unreadable entry is simply a miss
            return None

    def _cache_write(self, url: str, body: bytes) -> None:
        path = self._cache_path(url)
        if path is None:
            return
        try:
            json.loads(body)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {
                        "fetched_at": self._clock(),
                        "url": url,
                        "body": body.decode("utf-8"),
                    }
                ),
                encoding="utf-8",
            )
            os.replace(tmp, path)
        # caching is best-effort and must never fail a fetch
        except Exception:  # noqa: BLE001
            return

    def _request(self, target: BolsaiTarget) -> tuple[int, str, bytes, str]:
        cached = self._cache_read(target.url)
        if cached is not None:
            self.cache_hits += 1
            return 200, "application/json", cached, target.url
        self.cache_misses += 1
        request = Request(
            target.url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "X-API-Key": self._api_key,
            },
            method="GET",
        )
        try:
            response = self._opener(request, timeout=self.timeout)
        except HTTPError as exc:
            if exc.code == 429:
                raise BolsaiRateLimitError(_rate_limit_message(exc)) from exc
            raise
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)

        headers = getattr(response, "headers", {})
        content_type = (
            str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        )

        body = response.read()
        final_url = str(
            response.geturl() if hasattr(response, "geturl") else target.url
        )
        if status_code == 200:
            self._cache_write(target.url, body)
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
