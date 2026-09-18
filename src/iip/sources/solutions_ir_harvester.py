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
