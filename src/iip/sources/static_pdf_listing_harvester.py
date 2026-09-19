"""HTTP transport for the static-PDF-listing document source -- a
plain GET of the fund's own document-listing page, no auth, no JS
rendering needed (see ``iip.sources.static_pdf_listing`` module
docstring)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .static_pdf_listing import (
    DEFAULT_EXTENSIONS,
    StaticDocument,
    StaticListingTarget,
    build_targets,
    fund_for_ticker,
    parse_pdf_links,
)


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
        self.last_errors: list[str] = []

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
        fund = fund_for_ticker(target.ticker)
        documents = parse_pdf_links(
            html, final_url, target.ticker, fund.extensions if fund else DEFAULT_EXTENSIONS
        )

        return FetchedListingPage(
            target=target,
            status_code=status_code,
            documents=documents,
            final_url=final_url,
        )

    def collect(
        self, ticker: str, *, years: tuple[int, ...] = ()
    ) -> tuple[StaticDocument, ...]:
        """Every document of ``ticker`` across all its registered pages (and, for a
        registration with a year parameter, across ``years``), deduplicated by URL
        in the order found. The FIRST page must succeed -- a failure there is real
        and propagates; a failing later page or year is recorded in ``last_errors``
        and skipped, so one flaky page does not lose the rest."""
        self.last_errors = []
        by_url: dict[str, StaticDocument] = {}
        for index, target in enumerate(build_targets(ticker, years)):
            try:
                page = self.fetch(target)
            # see docstring: only the first page is mandatory
            except Exception as exc:  # noqa: BLE001
                if index == 0:
                    raise
                self.last_errors.append(f"{target.url}: {type(exc).__name__}: {exc}")
                continue
            for document in page.documents:
                by_url.setdefault(document.url, document)
        return tuple(by_url.values())
