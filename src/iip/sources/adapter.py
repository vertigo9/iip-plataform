"""Adapter from source harvest results into Atlas documents."""

from __future__ import annotations

from .models import AtlasDocument


class AtlasDocumentAdapter:
    """Normalize a fetched source document into Atlas' canonical model."""

    @staticmethod
    def _normalize_content_type(value: str | None) -> str:
        value = (value or "").strip().casefold()
        return value.split(";", 1)[0].strip()

    def from_fetched(self, fetched) -> AtlasDocument:
        """Convert a FetchedDocument-like object without coupling to its class."""
        target = fetched.target
        body = bytes(fetched.body)

        return AtlasDocument.build(
            ticker=target.ticker,
            provider=target.provider,
            role=target.role,
            url=target.url,
            final_url=fetched.final_url or target.url,
            content_type=self._normalize_content_type(fetched.content_type),
            status_code=fetched.status_code,
            body=body,
            discovered_year=target.year,
        )
