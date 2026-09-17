from __future__ import annotations

from typing import Any

from iip.analysis import AnalysisReport, Pillar
from iip.decision.thesis_exit_gate import GateStatus


def _pillar_indicators(
    report: AnalysisReport,
    pillar: Pillar,
) -> dict[str, Any]:
    for pillar_score in report.pillar_scores:
        if pillar_score.pillar == pillar:
            return dict(pillar_score.indicators)

    return {}


def _has_economic_evidence(indicators: dict[str, Any]) -> bool:
    return bool(indicators)


def _fundamentals_status(report: AnalysisReport) -> GateStatus:
    indicators = {}

    for pillar in (
        Pillar.CASH_FLOW,
        Pillar.BUSINESS_MODEL,
        Pillar.GROWTH,
    ):
        indicators.update(_pillar_indicators(report, pillar))

    if not _has_economic_evidence(indicators):
        return GateStatus.UNKNOWN

    return GateStatus.ATTENTION


def _balance_sheet_status(report: AnalysisReport) -> GateStatus:
    indicators = _pillar_indicators(report, Pillar.RESILIENCE)

    if not _has_economic_evidence(indicators):
        return GateStatus.UNKNOWN

    return GateStatus.ATTENTION


def _dividends_status(report: AnalysisReport) -> GateStatus:
    indicators = _pillar_indicators(report, Pillar.DIVIDENDS)

    if not _has_economic_evidence(indicators):
        return GateStatus.UNKNOWN

    return GateStatus.ATTENTION


def _governance_status(report: AnalysisReport) -> GateStatus:
    indicators = _pillar_indicators(report, Pillar.GOVERNANCE)

    if not _has_economic_evidence(indicators):
        return GateStatus.UNKNOWN

    return GateStatus.ATTENTION


def adapt_analysis_report_to_thesis_gates(
    report: AnalysisReport,
) -> dict[str, GateStatus]:
    """
    Translate existing AnalysisReport information into the six
    Thesis Exit gate statuses.

    This first implementation is intentionally conservative.

    It does not:
    - calculate new financial metrics;
    - invent economic thresholds;
    - calculate valuation;
    - calculate Opportunity Score;
    - create portfolio decisions;
    - create ThesisExitAssessment.

    UNKNOWN is preferred whenever the existing AnalysisReport does
    not contain sufficient semantic evidence.
    """

    return {
        "fundamentals": _fundamentals_status(report),
        "balance_sheet": _balance_sheet_status(report),
        "valuation": GateStatus.UNKNOWN,
        "dividends": _dividends_status(report),
        "governance": _governance_status(report),
        "opportunity_cost": GateStatus.UNKNOWN,
    }
