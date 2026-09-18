"""HTTP transport for the static-PDF-listing document source -- a
plain GET of the fund's own document-listing page, no auth, no JS
rendering needed (see ``iip.sources.static_pdf_listing`` module
docstring)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .static_pdf_listing import StaticDocument, StaticListingTarget, parse_pdf_links


@dataclass(frozen=True)
class FetchedListingPage:
    target: StaticListingTarget
    status_code: int
    documents: tuple[StaticDocument, ...]
    final_url: str = ""


class StaticPdfListingHTTPHarvester:
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

    def fetch(self, target: StaticListingTarget) -> FetchedListingPage:
        request = Request(
            target.url, headers={"User-Agent": self.user_agent}, method="GET"
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        body = response.read()
        final_url = str(response.geturl() if hasattr(response, "geturl") else target.url)

        html = body.decode("utf-8", errors="replace")
        documents = parse_pdf_links(html, final_url, target.ticker)

        return FetchedListingPage(
            target=target,
            status_code=status_code,
            documents=documents,
            final_url=final_url,
        )
