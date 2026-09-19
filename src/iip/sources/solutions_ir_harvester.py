"""HTTP transport for the Solutions IR document API -- a plain GET,
no auth, confirmed live for BTCI11 (see
``iip.sources.solutions_ir`` module docstring)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .solutions_ir import (
    SolutionsIrDocument,
    SolutionsIrTarget,
    build_documents_target,
    build_site_targets,
    company_for_ticker,
    parse_documents_response,
)


@dataclass(frozen=True)
class FetchedSolutionsIrDocuments:
    target: SolutionsIrTarget
    status_code: int
    documents: tuple[SolutionsIrDocument, ...]


class SolutionsIrHTTPHarvester:
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

    def fetch(self, target: SolutionsIrTarget) -> FetchedSolutionsIrDocuments:
        request = Request(
            target.url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        body = response.read()
        documents = parse_documents_response(body, target.ticker)

        return FetchedSolutionsIrDocuments(
            target=target, status_code=status_code, documents=documents
        )

    def collect(
        self, ticker: str, *, years: tuple[int, ...] = ()
    ) -> tuple[SolutionsIrDocument, ...]:
        """Every document of ``ticker``, whichever endpoint shape it is registered
        with: one call for a fund; one call per year in ``years`` for a company
        site (deduplicated by URL, newest first)."""
        company = company_for_ticker(ticker)
        if company is None:
            raise ValueError(f"no Solutions IR config registered for ticker {ticker!r}")
        if not company.is_site:
            return self.fetch(build_documents_target(ticker)).documents
        if not years:
            raise ValueError("years is required for a company site")
        by_url: dict[str, SolutionsIrDocument] = {}
        for target in build_site_targets(ticker, years):
            for document in self.fetch(target).documents:
                by_url.setdefault(document.url, document)
        return tuple(
            sorted(
                by_url.values(),
                key=lambda d: (d.year, d.date, d.category_sigla),
                reverse=True,
            )
        )
