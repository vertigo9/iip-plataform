"""HTTP transport for IIP document discovery targets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .xp_asset import DocumentTarget


@dataclass(frozen=True)
class FetchedDocument:
    target: DocumentTarget
    status_code: int
    content_type: str
    body: bytes
    final_url: str


class XPAssetHTTPHarvester:
    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        *,
        timeout: float = 20.0,
        user_agent: str = "IIP-D-OBSIDIAN/1.0",
    ) -> None:
        self._opener = opener or urlopen
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self, target: DocumentTarget) -> FetchedDocument:
        request = Request(
            target.url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/pdf,application/xhtml+xml,*/*;q=0.8",
            },
            method="GET",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        headers = getattr(response, "headers", {})
        content_type = (
            str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        )
        body = response.read()
        final_url = str(
            response.geturl() if hasattr(response, "geturl") else target.url
        )
        return FetchedDocument(target, status_code, content_type, body, final_url)

    def fetch_many(
        self, targets: tuple[DocumentTarget, ...]
    ) -> tuple[FetchedDocument, ...]:
        return tuple(self.fetch(target) for target in targets)
