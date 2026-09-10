"""HTTP transport for MZIQ targets (POST with JSON body).

No authentication needed — confirmed live against ABC Brasil's IR
site. Same injectable-``opener`` pattern as the other harvesters.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.request import Request, urlopen

from .mziq import (
    MziqDocument,
    MziqTarget,
    parse_documents_response,
    parse_years_response,
)


class MziqHTTPHarvester:
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

    def _post(self, target: MziqTarget) -> tuple[int, bytes]:
        data = json.dumps(target.body).encode("utf-8")
        request = Request(
            target.url,
            data=data,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        response = self._opener(request, timeout=self.timeout)
        raw_status = getattr(response, "status", 200)
        status_code = 200 if raw_status is None else int(raw_status)
        return status_code, response.read()

    def fetch_years(self, target: MziqTarget) -> tuple[int, ...]:
        _, body = self._post(target)
        return parse_years_response(body)

    def fetch_documents(self, target: MziqTarget) -> tuple[MziqDocument, ...]:
        _, body = self._post(target)
        return parse_documents_response(body)
