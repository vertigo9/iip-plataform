"""Enterprise consolidation pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .consolidator import consolidate
from .executive import ExecutiveConsolidation
from .models import ConsolidationInput


@dataclass(frozen=True)
class EnterprisePipelineInput:
    as_of: str
    consolidation: ConsolidationInput
    release_ready: bool


def run(data: EnterprisePipelineInput) -> ExecutiveConsolidation:
    result = consolidate(data.consolidation)
    return ExecutiveConsolidation(
        as_of=data.as_of,
        result=result,
        release_ready=bool(data.release_ready and result.consistent),
    )
