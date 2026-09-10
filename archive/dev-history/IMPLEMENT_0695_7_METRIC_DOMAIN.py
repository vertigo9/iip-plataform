from pathlib import Path

ROOT = Path.cwd()
SRC = ROOT / "src" / "iip" / "intelligence"
TESTS = ROOT / "tests" / "intelligence"

SRC.mkdir(parents=True, exist_ok=True)
TESTS.mkdir(parents=True, exist_ok=True)

MODULE = '''from __future__ import annotations

"""Historical metric evidence domain model for IIP 0695.7.

Side-effect free:
- no Obsidian writes;
- no metric promotion;
- original ticker and lineage remain explicit.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class EvidenceSourceRole(StrEnum):
    DOCUMENT = "DOCUMENT"
    DISTRIBUTION = "DISTRIBUTION"
    NAV_PL = "NAV_PL"
    RESULT = "RESULT"
    PORTFOLIO_CREDIT = "PORTFOLIO_CREDIT"
    EVENT = "EVENT"


class PromotionStatus(StrEnum):
    HOLD = "HOLD"
    REVIEW = "REVIEW"
    ELIGIBLE = "ELIGIBLE"


class LineageStatus(StrEnum):
    CURRENT = "CURRENT"
    HISTORICAL_PREDECESSOR = "HISTORICAL_PREDECESSOR"
    UNKNOWN = "UNKNOWN"


class UnitStatus(StrEnum):
    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"
    MISSING = "MISSING"


class PeriodStatus(StrEnum):
    EXPLICIT = "EXPLICIT"
    SUPPORTED = "SUPPORTED"
    MISSING = "MISSING"


@dataclass(frozen=True)
class TickerLineage:
    original_ticker: str
    canonical_ticker: str
    status: LineageStatus = LineageStatus.CURRENT

    def __post_init__(self) -> None:
        if not self.original_ticker.strip():
            raise ValueError("original_ticker must not be empty")
        if not self.canonical_ticker.strip():
            raise ValueError("canonical_ticker must not be empty")

    @property
    def changed(self) -> bool:
        return self.original_ticker.upper() != self.canonical_ticker.upper()


@dataclass(frozen=True)
class MetricObservation:
    metric_name: str
    value: float
    unit: str | None
    scale: str | None
    period: str | None
    period_status: PeriodStatus
    unit_status: UnitStatus

    def __post_init__(self) -> None:
        if not self.metric_name.strip():
            raise ValueError("metric_name must not be empty")
        if self.period_status is PeriodStatus.MISSING and self.period:
            raise ValueError("period cannot be present when period_status=MISSING")
        if self.unit_status is UnitStatus.EXPLICIT and not self.unit:
            raise ValueError("explicit unit requires unit")
        if self.unit_status is UnitStatus.MISSING and self.unit:
            raise ValueError("missing unit status cannot carry unit")
        if self.value != self.value:
            raise ValueError("value cannot be NaN")


@dataclass(frozen=True)
class HistoricalMetricEvidence:
    evidence_id: str
    document_id: str
    document_hash: str | None
    original_ticker: str
    canonical_ticker: str
    lineage: TickerLineage
    source_role: EvidenceSourceRole
    source_title: str
    source_date: date | None
    observation: MetricObservation
    confidence: float
    source_locator: str | None = None
    relevant_fact: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id must not be empty")
        if not self.document_id.strip():
            raise ValueError("document_id must not be empty")
        if not self.original_ticker.strip():
            raise ValueError("original_ticker must not be empty")
        if not self.canonical_ticker.strip():
            raise ValueError("canonical_ticker must not be empty")
        if not self.source_title.strip():
            raise ValueError("source_title must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.original_ticker.upper() != self.lineage.original_ticker.upper():
            raise ValueError("original ticker conflicts with lineage")
        if self.canonical_ticker.upper() != self.lineage.canonical_ticker.upper():
            raise ValueError("canonical ticker conflicts with lineage")


@dataclass(frozen=True)
class MetricPromotionAssessment:
    evidence: HistoricalMetricEvidence
    status: PromotionStatus
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def eligible(self) -> bool:
        return self.status is PromotionStatus.ELIGIBLE


def assess_promotion(evidence: HistoricalMetricEvidence) -> MetricPromotionAssessment:
    """Apply conservative 0695.7 prerequisites."""

    reasons: list[str] = []

    if evidence.observation.period_status is not PeriodStatus.EXPLICIT:
        reasons.append("period_not_explicit")

    if evidence.observation.unit_status is not UnitStatus.EXPLICIT:
        reasons.append("unit_not_explicit")

    if evidence.confidence < 0.80:
        reasons.append("confidence_below_0_80")

    if not evidence.observation.metric_name.strip():
        reasons.append("metric_name_missing")

    if evidence.lineage.status is LineageStatus.UNKNOWN:
        reasons.append("lineage_unknown")

    if reasons:
        return MetricPromotionAssessment(
            evidence=evidence,
            status=PromotionStatus.REVIEW,
            reasons=tuple(reasons),
        )

    return MetricPromotionAssessment(
        evidence=evidence,
        status=PromotionStatus.ELIGIBLE,
        reasons=("all_promotion_prerequisites_satisfied",),
    )
'''

TESTS_TEXT = '''from datetime import date

from iip.intelligence.metric_evidence import (
    EvidenceSourceRole,
    HistoricalMetricEvidence,
    LineageStatus,
    MetricObservation,
    PeriodStatus,
    PromotionStatus,
    TickerLineage,
    UnitStatus,
    assess_promotion,
)


def make_evidence(**overrides):
    data = {
        "evidence_id": "EV-0695-TEST-001",
        "document_id": "DOC-001",
        "document_hash": "abc123",
        "original_ticker": "CVBI11",
        "canonical_ticker": "PCIP11",
        "lineage": TickerLineage(
            original_ticker="CVBI11",
            canonical_ticker="PCIP11",
            status=LineageStatus.HISTORICAL_PREDECESSOR,
        ),
        "source_role": EvidenceSourceRole.DISTRIBUTION,
        "source_title": "Informe de rendimentos",
        "source_date": date(2024, 12, 31),
        "observation": MetricObservation(
            metric_name="distribution_per_share",
            value=0.80,
            unit="BRL/share",
            scale="1x",
            period="2024-12",
            period_status=PeriodStatus.EXPLICIT,
            unit_status=UnitStatus.EXPLICIT,
        ),
        "confidence": 0.95,
        "source_locator": "page:1",
        "relevant_fact": "Distribution amount",
    }
    data.update(overrides)
    return HistoricalMetricEvidence(**data)


def test_cvbi11_lineage_is_explicit():
    evidence = make_evidence()
    assert evidence.original_ticker == "CVBI11"
    assert evidence.canonical_ticker == "PCIP11"
    assert evidence.lineage.changed is True
    assert evidence.lineage.status is LineageStatus.HISTORICAL_PREDECESSOR


def test_explicit_period_and_unit_are_eligible():
    result = assess_promotion(make_evidence())
    assert result.status is PromotionStatus.ELIGIBLE
    assert result.eligible is True


def test_missing_unit_requires_review():
    observation = MetricObservation(
        metric_name="distribution_per_share",
        value=0.80,
        unit=None,
        scale=None,
        period="2024-12",
        period_status=PeriodStatus.EXPLICIT,
        unit_status=UnitStatus.MISSING,
    )
    result = assess_promotion(make_evidence(observation=observation))
    assert result.status is PromotionStatus.REVIEW
    assert "unit_not_explicit" in result.reasons


def test_low_confidence_requires_review():
    result = assess_promotion(make_evidence(confidence=0.79))
    assert result.status is PromotionStatus.REVIEW
    assert "confidence_below_0_80" in result.reasons
'''

module_path = SRC / "metric_evidence.py"
test_path = TESTS / "test_metric_evidence.py"

module_path.write_text(MODULE, encoding="utf-8")
test_path.write_text(TESTS_TEXT, encoding="utf-8")

print("0695.7 DOMAIN MODEL CREATED")
print(f"Module: {module_path}")
print(f"Test:   {test_path}")
print("Vault changed: NO")
print("Metric promoted: NO")
print("")
print("Run:")
print("  python -m pytest .\\tests\\intelligence\\test_metric_evidence.py -q")
