from datetime import date

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
