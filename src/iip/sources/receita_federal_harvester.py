"""HTTP transport for BrasilAPI CNPJ targets.

No authentication required (BrasilAPI is open, no token/key). Same
injectable-``opener`` pattern as the other harvesters — no real
network call in tests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .receita_federal import CnpjRecord, CnpjTarget, parse_cnpj_response


@dataclass(frozen=True)
class FetchedCnpj:
    target: CnpjTarget
    status_code: int
    record: CnpjRecord


class ReceitaFederalHTTPHarvester:
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

    def fetch(self, target: CnpjTarget) -> FetchedCnpj:
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
        record = parse_cnpj_response(body)
        return FetchedCnpj(target=target, status_code=status_code, record=record)

    def fetch_many(self, targets: tuple[CnpjTarget, ...]) -> tuple[FetchedCnpj, ...]:
        return tuple(self.fetch(target) for target in targets)
