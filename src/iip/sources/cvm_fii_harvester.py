"""HTTP transport for CVM FII monthly report ZIP downloads.

No authentication needed — dados.cvm.gov.br is a plain open-data file
repository. Same injectable-``opener`` pattern as the other
harvesters, so tests never download a real file.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from urllib.request import Request, urlopen

from .cvm_fii import (
    CvmFiiTarget,
    FiiAtivoPassivo,
    FiiComplemento,
    FiiGeral,
    parse_ativo_passivo,
    parse_complemento,
    parse_geral,
)


@dataclass(frozen=True)
class FetchedFiiReport:
    target: CvmFiiTarget
    status_code: int
    geral: tuple[FiiGeral, ...]
    ativo_passivo: tuple[FiiAtivoPassivo, ...]
    complemento: tuple[FiiComplemento, ...]
    content_type: str = ""
    body: bytes = b""
    final_url: str = ""


class CvmFiiHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 60.0,  # arquivos anuais sao grandes (MB), timeout maior
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: CvmFiiTarget) -> FetchedFiiReport:
        request = Request(
            target.url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/zip",
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
            response.geturl()
            if hasattr(response, "geturl")
            else target.url
        )

        return FetchedFiiReport(
            target=target,
            status_code=status_code,
            geral=parse_geral(body),
            ativo_passivo=parse_ativo_passivo(body),
            complemento=parse_complemento(body),
            content_type=content_type,
            body=body,
            final_url=final_url,
        )


class CachedCvmFiiHarvester:
    """Memoizes ``CvmFiiHTTPHarvester.fetch`` per year for the life of the
    instance. One CVM FII ZIP covers EVERY fund, so a portfolio run would
    otherwise download the same file once per fund. The raw ``body`` is dropped
    from the cached copy; only the parsed rows are needed."""

    def __init__(self, inner: CvmFiiHTTPHarvester | None = None) -> None:
        self._inner = inner or CvmFiiHTTPHarvester()
        self._cache: dict[int, FetchedFiiReport] = {}

    def fetch(self, target: CvmFiiTarget) -> FetchedFiiReport:
        key = target.ano
        if key not in self._cache:
            self._cache[key] = replace(self._inner.fetch(target), body=b"")
        return self._cache[key]


_ACTIVE_FII_CACHE: ContextVar[CachedCvmFiiHarvester | None] = ContextVar(
    "iip_active_fii_cache", default=None
)


def active_fii_cache() -> CachedCvmFiiHarvester | None:
    return _ACTIVE_FII_CACHE.get()


@contextmanager
def shared_fii_cache() -> Iterator[CachedCvmFiiHarvester]:
    cache = CachedCvmFiiHarvester()
    token = _ACTIVE_FII_CACHE.set(cache)
    try:
        yield cache
    finally:
        _ACTIVE_FII_CACHE.reset(token)
