"""Operational checkpoint for the 101→200 block."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationalCheckpoint:
    normalized_documents: int
    atlas_ingested: int
    providers_ready: int
    providers_mapped: int
    legacy_suite_green: bool

    @property
    def safe_to_continue(self) -> bool:
        return self.legacy_suite_green and self.normalized_documents > 0
