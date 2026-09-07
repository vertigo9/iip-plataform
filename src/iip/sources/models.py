"""Canonical Atlas document contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256


@dataclass(frozen=True)
class AtlasDocument:
    """Canonical document representation passed downstream by Atlas."""

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
        content_hash = sha256(body).hexdigest()
        year_part = str(discovered_year) if discovered_year is not None else "na"
        document_id = f"{provider}:{ticker}:{year_part}:{content_hash[:16]}"
        return cls(
            document_id=document_id,
            ticker=ticker.strip().upper(),
            provider=provider.strip().casefold(),
            role=role.strip().casefold(),
            url=url.strip(),
            final_url=final_url.strip(),
            content_type=content_type.strip().casefold(),
            status_code=int(status_code),
            body=body,
            content_hash=content_hash,
            discovered_year=discovered_year,
            ingested_at=datetime.now(UTC),
        )
