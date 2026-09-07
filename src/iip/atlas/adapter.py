"""Adapter from source fetch results into Atlas documents."""

from __future__ import annotations

from .models import AtlasDocument


class AtlasDocumentAdapter:
    """Normalize a FetchedDocument-like value into AtlasDocument."""

    @staticmethod
    def _normalize_content_type(value: str | None) -> str:
        return (value or "").split(";", 1)[0].strip().casefold()

    def from_fetched(self, fetched) -> AtlasDocument:
        target = fetched.target
        return AtlasDocument.build(
            ticker=target.ticker,
            provider=target.provider,
            role=target.role,
            url=target.url,
            final_url=fetched.final_url or target.url,
            content_type=self._normalize_content_type(fetched.content_type),
            status_code=fetched.status_code,
            body=fetched.body,
            discovered_year=target.year,
        )
