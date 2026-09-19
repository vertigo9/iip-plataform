from iip.decision.decision_engine import decide
from iip.decision.models import IntelligenceInput, Verdict
from iip.decision.thesis_exit_gate import (
    GateStatus,
    ThesisExitState,
    assess_thesis_exit,
)


def test_all_pass_is_intact():
    assessment = assess_thesis_exit(
        fundamentals=GateStatus.PASS,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.PASS,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.PASS,
    )

    assert assessment.state is ThesisExitState.INTACT
    assert not assessment.should_exit


def test_unknown_is_not_fail():
    assessment = assess_thesis_exit(
        fundamentals=GateStatus.UNKNOWN,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.PASS,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.PASS,
    )

    assert assessment.state is ThesisExitState.INSUFFICIENT_EVIDENCE
    assert assessment.failed_gates == ()
    assert "fundamentals" in assessment.unknown_gates


def test_critical_failure_breaks_thesis():
    assessment = assess_thesis_exit(
        fundamentals=GateStatus.FAIL,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.PASS,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.PASS,
    )

    assert assessment.state is ThesisExitState.BREAK
    assert assessment.critical_failure
    assert assessment.should_exit


def test_two_noncritical_failures_break():
    assessment = assess_thesis_exit(
        fundamentals=GateStatus.PASS,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.FAIL,
        dividends=GateStatus.FAIL,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.PASS,
    )

    assert assessment.state is ThesisExitState.BREAK
    assert assessment.should_exit


def test_attention_is_review_not_automatic_sale():
    assessment = assess_thesis_exit(
        fundamentals=GateStatus.PASS,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.ATTENTION,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.PASS,
    )

    assert assessment.state is ThesisExitState.REVIEW
    assert not assessment.should_exit
    assert assessment.should_reduce


def test_opportunity_cost_alone_is_review():
    assessment = assess_thesis_exit(
        fundamentals=GateStatus.PASS,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.PASS,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.ATTENTION,
    )

    assert assessment.state is ThesisExitState.REVIEW
    assert not assessment.should_exit


def _item(**kwargs):
    values = {
        "ticker": "TEST3",
        "thesis_signal": "intact",
        "risk_level": "medium",
        "valuation_score": 8.0,
        "dividend_score": 8.0,
        "quality_score": 8.0,
        "opportunity_score": 8.0,
        "evidence": (),
    }
    values.update(kwargs)
    return IntelligenceInput(**values)


def test_decision_without_thesis_exit_defaults_to_none():
    decision = decide(_item())

    assert decision.ticker == "TEST3"
    assert decision.thesis_exit is None


def test_decision_break_has_exit_precedence():
    assessment = assess_thesis_exit(
        fundamentals=GateStatus.FAIL,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.PASS,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.PASS,
    )

    decision = decide(_item(thesis_exit=assessment))

    assert decision.verdict is Verdict.VENDER
    assert decision.thesis_exit is assessment
    assert any("thesis_exit=BREAK" in reason for reason in decision.reasons)
