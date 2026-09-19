"""HTTP transport for the CPFL IR results center -- a plain GET, no auth (see
``iip.sources.cpfl_ri``)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .cpfl_ri import CpflDocument, CpflTarget, build_results_target, parse_results_page


@dataclass(frozen=True)
class FetchedCpflDocuments:
    target: CpflTarget
    status_code: int
    documents: tuple[CpflDocument, ...]


class CpflRiHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 60.0,  # the page is ~430 KB of HTML
        user_agent: str = "Mozilla/5.0 (compatible; IIP-D-OBSIDIAN/1.0)",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: CpflTarget | None = None) -> FetchedCpflDocuments:
        target = target or build_results_target("CPFE3")
        request = Request(
            target.url, headers={"User-Agent": self.user_agent}, method="GET"
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        html = response.read().decode("utf-8", errors="replace")
        return FetchedCpflDocuments(
            target=target,
            status_code=status_code,
            documents=parse_results_page(html, target.ticker),
        )
