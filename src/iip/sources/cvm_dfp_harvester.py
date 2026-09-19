"""HTTP transport for CVM DFP annual-statement ZIP downloads.

No authentication needed — dados.cvm.gov.br is a plain open-data file
repository. Same injectable-``opener`` pattern as the other harvesters,
so tests never download a real file.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from urllib.request import Request, urlopen

from .cvm_dfp import (
    CvmDfpTarget,
    DfpRow,
    parse_bpa_con,
    parse_bpa_ind,
    parse_bpp_con,
    parse_bpp_ind,
    parse_dfc_con,
    parse_dfc_ind,
    parse_dre_con,
    parse_dre_ind,
)


@dataclass(frozen=True)
class FetchedDfpYear:
    target: CvmDfpTarget
    status_code: int
    bpa_con: tuple[DfpRow, ...]
    bpa_ind: tuple[DfpRow, ...]
    bpp_con: tuple[DfpRow, ...]
    bpp_ind: tuple[DfpRow, ...]
    dre_con: tuple[DfpRow, ...]
    dre_ind: tuple[DfpRow, ...]
    content_type: str = ""
    body: bytes = b""
    final_url: str = ""
    dfc_con: tuple[DfpRow, ...] = ()
    dfc_ind: tuple[DfpRow, ...] = ()


class CvmDfpHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 90.0,  # arquivo anual e grande (10-13MB), timeout maior
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: CvmDfpTarget) -> FetchedDfpYear:
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
        content_type = (
            str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        )

        body = response.read()

        final_url = str(
            response.geturl() if hasattr(response, "geturl") else target.url
        )

        return FetchedDfpYear(
            target=target,
            status_code=status_code,
            bpa_con=parse_bpa_con(body),
            bpa_ind=parse_bpa_ind(body),
            bpp_con=parse_bpp_con(body),
            bpp_ind=parse_bpp_ind(body),
            dre_con=parse_dre_con(body),
            dre_ind=parse_dre_ind(body),
            dfc_con=parse_dfc_con(body),
            dfc_ind=parse_dfc_ind(body),
            content_type=content_type,
            body=body,
            final_url=final_url,
        )


class CachedCvmDfpHarvester:
    """Memoizes ``CvmDfpHTTPHarvester.fetch`` per fiscal year for the life of
    the instance. A DFP ZIP covers EVERY listed company, so in a portfolio run
    the same year is otherwise re-downloaded (~13 MB) once per equity. The raw
    ``body`` is dropped from the cached copy to keep memory bounded; only the
    parsed rows are needed."""

    def __init__(self, inner: CvmDfpHTTPHarvester | None = None) -> None:
        self._inner = inner or CvmDfpHTTPHarvester()
        self._cache: dict[int, FetchedDfpYear] = {}

    def fetch(self, target: CvmDfpTarget) -> FetchedDfpYear:
        if target.ano not in self._cache:
            self._cache[target.ano] = replace(self._inner.fetch(target), body=b"")
        return self._cache[target.ano]


_ACTIVE_CACHE: ContextVar[CachedCvmDfpHarvester | None] = ContextVar(
    "iip_active_dfp_cache", default=None
)


def active_dfp_cache() -> CachedCvmDfpHarvester | None:
    """The shared cache of the enclosing ``shared_dfp_cache()`` block, if any."""
    return _ACTIVE_CACHE.get()


@contextmanager
def shared_dfp_cache() -> Iterator[CachedCvmDfpHarvester]:
    """Within this block, ``fetch_equity_template_live`` reuses one cache, so a
    batch downloads each fiscal year's DFP once instead of once per equity."""
    cache = CachedCvmDfpHarvester()
    token = _ACTIVE_CACHE.set(cache)
    try:
        yield cache
    finally:
        _ACTIVE_CACHE.reset(token)


def with_shared_dfp_cache(func: Callable) -> Callable:
    """Decorator form of ``shared_dfp_cache`` for batch entry points."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with shared_dfp_cache():
            return func(*args, **kwargs)

    return wrapper
