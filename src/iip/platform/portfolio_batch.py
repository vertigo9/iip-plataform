"""Deterministic batching for large portfolio runs."""

from __future__ import annotations

from collections.abc import Iterable, Iterator


def batches(items: Iterable[str], size: int) -> Iterator[tuple[str, ...]]:
    if size <= 0:
        raise ValueError("size must be positive")
    current: list[str] = []
    for item in items:
        current.append(item)
        if len(current) == size:
            yield tuple(current)
            current.clear()
    if current:
        yield tuple(current)


def plan_batches(tickers: Iterable[str], size: int = 10) -> tuple[tuple[str, ...], ...]:
    return tuple(batches((ticker.upper() for ticker in tickers), size))
