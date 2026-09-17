from iip.analysis import AnalysisReport, Pillar, PillarScore
from iip.decision.thesis_exit_gate import GateStatus
from iip.decision.thesis_semantic_adapter import (
    adapt_analysis_report_to_thesis_gates,
)


def make_report(
    *,
    fundamentals_indicators=None,
    balance_indicators=None,
    dividends_indicators=None,
    governance_indicators=None,
):
    report = AnalysisReport(
        asset_symbol="TEST3",
        asset_type="equity",
    )

    if fundamentals_indicators is not None:
        report.add_pillar(
            PillarScore(
                pillar=Pillar.CASH_FLOW,
                score=80.0,
                weight=1.0,
                indicators=fundamentals_indicators,
                comments="test",
            )
        )

    if balance_indicators is not None:
        report.add_pillar(
            PillarScore(
                pillar=Pillar.RESILIENCE,
                score=80.0,
                weight=1.0,
                indicators=balance_indicators,
                comments="test",
            )
        )

    if dividends_indicators is not None:
        report.add_pillar(
            PillarScore(
                pillar=Pillar.DIVIDENDS,
                score=80.0,
                weight=1.0,
                indicators=dividends_indicators,
                comments="test",
            )
        )

    if governance_indicators is not None:
        report.add_pillar(
            PillarScore(
                pillar=Pillar.GOVERNANCE,
                score=80.0,
                weight=1.0,
                indicators=governance_indicators,
                comments="test",
            )
        )

    return report


def test_adapter_returns_all_six_thesis_exit_gates():
    report = make_report()

    result = adapt_analysis_report_to_thesis_gates(report)

    assert set(result) == {
        "fundamentals",
        "balance_sheet",
        "valuation",
        "dividends",
        "governance",
        "opportunity_cost",
    }


def test_missing_economic_evidence_returns_unknown():
    report = make_report()

    result = adapt_analysis_report_to_thesis_gates(report)

    assert result["fundamentals"] == GateStatus.UNKNOWN
    assert result["balance_sheet"] == GateStatus.UNKNOWN
    assert result["dividends"] == GateStatus.UNKNOWN
    assert result["governance"] == GateStatus.UNKNOWN


def test_single_deterioration_does_not_become_fail():
    report = make_report(
        fundamentals_indicators={
            "net_income_growth": -5.0,
        }
    )

    result = adapt_analysis_report_to_thesis_gates(report)

    assert result["fundamentals"] != GateStatus.FAIL


def test_low_dividend_yield_alone_does_not_mean_fail():
    report = make_report(
        dividends_indicators={
            "dividend_yield": 4.0,
        }
    )

    result = adapt_analysis_report_to_thesis_gates(report)

    assert result["dividends"] != GateStatus.FAIL


def test_low_pillar_score_alone_does_not_create_economic_fail():
    report = make_report(
        fundamentals_indicators={},
    )

    report.pillar_scores[0] = PillarScore(
        pillar=Pillar.CASH_FLOW,
        score=20.0,
        weight=1.0,
        indicators={},
        comments="test",
    )

    result = adapt_analysis_report_to_thesis_gates(report)

    assert result["fundamentals"] == GateStatus.UNKNOWN


def test_adapter_does_not_return_portfolio_decision():
    report = make_report()

    result = adapt_analysis_report_to_thesis_gates(report)

    allowed = {
        GateStatus.PASS,
        GateStatus.ATTENTION,
        GateStatus.FAIL,
        GateStatus.UNKNOWN,
    }

    assert all(value in allowed for value in result.values())
