"""Atlas gateway boundary for normalized documents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .normalization import NormalizedDocument


@dataclass(frozen=True)
class AtlasIngestResult:
    document_id: str
    success: bool
    value: Any = None
    error: str | None = None


class AtlasGateway:
    def __init__(self, ingest_fn: Callable[[NormalizedDocument], Any]) -> None:
        self.ingest_fn = ingest_fn

    def ingest(self, document: NormalizedDocument) -> AtlasIngestResult:
        try:
            return AtlasIngestResult(
                document.document_id,
                True,
                self.ingest_fn(document),
            )
        except Exception as exc:  # noqa: BLE001 — isola falha da ingestao num AtlasIngestResult, nao deixa propagar
            return AtlasIngestResult(
                document.document_id,
                False,
                error=f"{type(exc).__name__}:{exc}",
            )
