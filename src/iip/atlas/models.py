"""Canonical Atlas document contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256


@dataclass(frozen=True)
class AtlasDocument:
    """Canonical normalized document emitted by an ingestion adapter."""

    document_id: str
    ticker: str
    provider: str
    role: str
    url: str
    final_url: str
    content_type: str
    status_code: int
    body: bytes
    content_hash: str
    discovered_year: int | None
    ingested_at: datetime

    @classmethod
    def build(
        cls,
        *,
        ticker: str,
        provider: str,
        role: str,
        url: str,
        final_url: str,
        content_type: str,
        status_code: int,
        body: bytes,
        discovered_year: int | None,
    ) -> AtlasDocument:
        payload = bytes(body)
        content_hash = sha256(payload).hexdigest()
        normalized_ticker = ticker.strip().upper()
        normalized_provider = provider.strip().casefold()
        normalized_role = role.strip().casefold()
        year_part = str(discovered_year) if discovered_year is not None else "na"
        document_id = (
            f"{normalized_provider}:{normalized_ticker}:{year_part}:{content_hash[:16]}"
        )

        return cls(
            document_id=document_id,
            ticker=normalized_ticker,
            provider=normalized_provider,
            role=normalized_role,
            url=url.strip(),
            final_url=(final_url or url).strip(),
            content_type=content_type.strip().casefold(),
            status_code=int(status_code),
            body=payload,
            content_hash=content_hash,
            discovered_year=discovered_year,
            ingested_at=datetime.now(UTC),
        )
