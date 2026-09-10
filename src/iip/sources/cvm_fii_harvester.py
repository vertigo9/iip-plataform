"""HTTP transport for CVM FII monthly report ZIP downloads.

No authentication needed — dados.cvm.gov.br is a plain open-data file
repository. Same injectable-``opener`` pattern as the other
harvesters, so tests never download a real file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
        body = response.read()

        return FetchedFiiReport(
            target=target,
            status_code=status_code,
            geral=parse_geral(body),
            ativo_passivo=parse_ativo_passivo(body),
            complemento=parse_complemento(body),
        )
