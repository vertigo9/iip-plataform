"""HTTP transport for CVM DFP annual-statement ZIP downloads.

No authentication needed — dados.cvm.gov.br is a plain open-data file
repository. Same injectable-``opener`` pattern as the other harvesters,
so tests never download a real file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
        content_type = str(
            headers.get("Content-Type", "")
        ).split(";", 1)[0].strip().lower()

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
