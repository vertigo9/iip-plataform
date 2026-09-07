"""End-to-end decision pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .decision_engine import decide
from .models import Decision, IntelligenceInput
from .validation import ValidationResult, validate_decision


@dataclass(frozen=True)
class DecisionPipelineResult:
    decision: Decision
    validation: ValidationResult


def run(item: IntelligenceInput) -> DecisionPipelineResult:
    decision = decide(item)
    return DecisionPipelineResult(
        decision=decision,
        validation=validate_decision(decision),
    )
