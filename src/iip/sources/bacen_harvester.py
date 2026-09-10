"""HTTP transport for BACEN SGS series targets.

Mirrors ``.harvester.XPAssetHTTPHarvester`` exactly: same injectable
``opener`` pattern (defaults to ``urllib.request.urlopen``), same
timeout/user-agent shape, so tests never need a real network call.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .bacen import BacenSeriesPoint, BacenSeriesTarget, parse_series_response


@dataclass(frozen=True)
class FetchedSeries:
    target: BacenSeriesTarget
    status_code: int
    points: tuple[BacenSeriesPoint, ...]


class BacenHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 20.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: BacenSeriesTarget) -> FetchedSeries:
        request = Request(
            target.url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        body = response.read()
        points = parse_series_response(body)
        return FetchedSeries(target=target, status_code=status_code, points=points)

    def fetch_many(
        self, targets: tuple[BacenSeriesTarget, ...]
    ) -> tuple[FetchedSeries, ...]:
        return tuple(self.fetch(target) for target in targets)
