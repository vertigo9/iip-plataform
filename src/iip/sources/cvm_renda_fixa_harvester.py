"""HTTP transport for CVM Fundos ICVM 555 (Informe Diário + Perfil Mensal).

No authentication needed. Same injectable-``opener`` pattern as the
other harvesters. Note the two targets need different handling:
Informe Diário is a ZIP, Perfil Mensal is a plain CSV — confirmed
live, not assumed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .cvm_renda_fixa import (
    CvmDiarioTarget,
    CvmPerfilTarget,
    InformeDiario,
    PerfilMensal,
    parse_diario_response,
    parse_perfil_response,
)


@dataclass(frozen=True)
class FetchedDiario:
    target: CvmDiarioTarget
    status_code: int
    informes: tuple[InformeDiario, ...]


@dataclass(frozen=True)
class FetchedPerfil:
    target: CvmPerfilTarget
    status_code: int
    perfis: tuple[PerfilMensal, ...]


class CvmRendaFixaHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 90.0,  # informe diario pode ter dezenas de MB
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def _get(self, url: str, accept: str) -> tuple[int, bytes]:
        request = Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": accept},
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        return status_code, response.read()

    def fetch_diario(self, target: CvmDiarioTarget) -> FetchedDiario:
        status_code, body = self._get(target.url, "application/zip")
        return FetchedDiario(
            target=target, status_code=status_code, informes=parse_diario_response(body)
        )

    def fetch_perfil(self, target: CvmPerfilTarget) -> FetchedPerfil:
        status_code, body = self._get(target.url, "text/csv")
        return FetchedPerfil(
            target=target, status_code=status_code, perfis=parse_perfil_response(body)
        )
