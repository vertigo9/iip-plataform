"""Scenario decision validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .decision_stability import assess
from .models import DecisionScenario
from .scenario_report import ScenarioReport
from .validation_gate import evaluate


@dataclass(frozen=True)
class ScenarioPipelineInput:
    as_of: str
    decisions: tuple[DecisionScenario, ...]
    evidence_complete: bool
    risk_acceptable: bool


@dataclass(frozen=True)
class ScenarioPipelineResult:
    report: ScenarioReport
    gate: object


def run(data: ScenarioPipelineInput) -> ScenarioPipelineResult:
    stability = tuple(assess(item) for item in data.decisions)
    report = ScenarioReport(data.as_of, stability)
    gate = evaluate(
        stable=report.changed_count == 0 and report.stable_count == len(stability),
        evidence_complete=data.evidence_complete,
        risk_acceptable=data.risk_acceptable,
    )
    return ScenarioPipelineResult(report, gate)
