"""HTTP transport for CVM FIAGRO monthly report ZIP downloads.

No authentication needed. Same injectable-``opener`` pattern as the
other harvesters.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .cvm_fiagro import (
    CvmFiagroTarget,
    FiagroInforme,
    FiagroSubclasse,
    parse_informe,
    parse_subclasse,
)


@dataclass(frozen=True)
class FetchedFiagroReport:
    target: CvmFiagroTarget
    status_code: int
    informes: tuple[FiagroInforme, ...]
    subclasses: tuple[FiagroSubclasse, ...]


class CvmFiagroHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 60.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: CvmFiagroTarget) -> FetchedFiagroReport:
        request = Request(
            target.url,
            headers={"User-Agent": self.user_agent, "Accept": "application/zip"},
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        body = response.read()

        return FetchedFiagroReport(
            target=target,
            status_code=status_code,
            informes=parse_informe(body),
            subclasses=parse_subclasse(body),
        )
