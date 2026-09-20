"""HTTP transport for IBGE Agregados targets.

Same injectable-``opener`` pattern as ``.bacen_harvester`` and
``.harvester`` — no real network call in tests.
"""

from __future__ import annotations

import gzip
from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .ibge import IbgeDataPoint, IbgeTarget, parse_agregados_response

_GZIP_MAGIC = bytes((0x1F, 0x8B))


def _maybe_gunzip(body: bytes) -> bytes:
    """O IBGE responde em gzip mesmo sem o cliente pedir (Content-Encoding: gzip); o urllib
    não descomprime sozinho. Reconhece pelo início do corpo (1f 8b), não só pelo cabeçalho.
    """
    return gzip.decompress(body) if body[:2] == _GZIP_MAGIC else body


@dataclass(frozen=True)
class FetchedAggregate:
    target: IbgeTarget
    status_code: int
    points: tuple[IbgeDataPoint, ...]


class IbgeHTTPHarvester:
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

    def fetch(self, target: IbgeTarget) -> FetchedAggregate:
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
        body = _maybe_gunzip(response.read())
        points = parse_agregados_response(body)
        return FetchedAggregate(target=target, status_code=status_code, points=points)

    def fetch_many(
        self, targets: tuple[IbgeTarget, ...]
    ) -> tuple[FetchedAggregate, ...]:
        return tuple(self.fetch(target) for target in targets)
