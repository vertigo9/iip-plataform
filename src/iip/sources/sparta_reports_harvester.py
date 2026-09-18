"""HTTP transport for Sparta's monthly report PDFs -- a plain static
file download, no auth, no JS rendering needed (unlike the Patria
MZIQ portal)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .sparta_reports import SpartaReportTarget, extract_cota_patrimonial


@dataclass(frozen=True)
class FetchedSpartaReport:
    target: SpartaReportTarget
    status_code: int
    body: bytes
    cota_patrimonial: float | None
    final_url: str = ""


class SpartaReportsHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 30.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: SpartaReportTarget) -> FetchedSpartaReport:
        request = Request(
            target.url, headers={"User-Agent": self.user_agent}, method="GET"
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        body = response.read()
        final_url = str(response.geturl() if hasattr(response, "geturl") else target.url)

        return FetchedSpartaReport(
            target=target,
            status_code=status_code,
            body=body,
            cota_patrimonial=extract_cota_patrimonial(body),
            final_url=final_url,
        )
