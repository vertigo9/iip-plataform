"""Enterprise executive consolidation report."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ConsolidationResult


@dataclass(frozen=True)
class ExecutiveConsolidation:
    as_of: str
    result: ConsolidationResult
    release_ready: bool
