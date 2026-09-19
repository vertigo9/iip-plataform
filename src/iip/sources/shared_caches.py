"""One switch for every per-run download cache a batch wants.

A portfolio run (refresh, analyze, value) fetches many positions whose data
comes from a handful of big CVM files that each cover EVERY company/fund (the
DFP ZIP for equities, the monthly FII ZIP for funds). Inside
``shared_fetch_caches()`` each of those is downloaded once per run instead of
once per position; outside it nothing is cached.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from .cvm_dfp_harvester import shared_dfp_cache
from .cvm_fii_harvester import shared_fii_cache


@contextmanager
def shared_fetch_caches() -> Iterator[None]:
    with shared_dfp_cache(), shared_fii_cache():
        yield


def with_shared_fetch_caches(func: Callable) -> Callable:
    """Decorator form for batch entry points."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with shared_fetch_caches():
            return func(*args, **kwargs)

    return wrapper
