from iip.decision.models import Decision, EvidenceRef, Verdict
from iip.decision.thesis_exit_gate import (
    GateStatus,
    ThesisExitAssessment,
    ThesisExitState,
)
from iip.integration.models import Action
from iip.portfolio.registry import PortfolioAsset


def _portfolio_asset(
    ticker: str = "HGRU11",
    asset_class: str = "fund",
) -> PortfolioAsset:
    return PortfolioAsset(
        ticker=ticker,
        asset_class=asset_class,
    )


def _thesis_exit() -> ThesisExitAssessment:
    return ThesisExitAssessment(
        fundamentals=GateStatus.PASS,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.ATTENTION,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.ATTENTION,
        state=ThesisExitState.REVIEW,
        failed_gates=(),
        attention_gates=("valuation", "opportunity_cost"),
        unknown_gates=(),
        critical_failure=False,
    )


def _decision(
    *,
    verdict: Verdict = Verdict.MANTER,
    score: float = 8.35,
    confidence: float = 0.87,
    evidence: tuple[EvidenceRef, ...] = (
        EvidenceRef("EV-001"),
        EvidenceRef("EV-002"),
        EvidenceRef("EV-002"),
        EvidenceRef("EV-003"),
    ),
    thesis_exit: ThesisExitAssessment | None = None,
) -> Decision:
    return Decision(
        ticker="HGRU11",
        verdict=verdict,
        score=score,
        confidence=confidence,
        reasons=("reason-1", "reason-2"),
        evidence=evidence,
        thesis_exit=thesis_exit,
    )


def test_decision_to_asset_signal_preserves_core_decision_fields():
    from iip.integration.decision_adapter import decision_to_asset_signal

    signal = decision_to_asset_signal(
        _decision(),
        _portfolio_asset(),
    )

    assert signal.ticker == "HGRU11"
    assert signal.decision_score == 8.35
    assert signal.confidence == 0.87
    assert signal.asset_class == "fund"


def test_decision_to_asset_signal_maps_verdict_to_action():
    from iip.integration.decision_adapter import decision_to_asset_signal

    expected = {
        Verdict.COMPRAR: Action.APORTAR,
        Verdict.MANTER: Action.MANTER,
        Verdict.AGUARDAR: Action.AGUARDAR,
        Verdict.REDUZIR: Action.REDUZIR,
        Verdict.VENDER: Action.VENDER,
    }

    for verdict, action in expected.items():
        signal = decision_to_asset_signal(
            _decision(verdict=verdict),
            _portfolio_asset(),
        )
        assert signal.action is action


def test_decision_to_asset_signal_preserves_unique_evidence_ids():
    from iip.integration.decision_adapter import decision_to_asset_signal

    signal = decision_to_asset_signal(
        _decision(),
        _portfolio_asset(),
    )

    assert signal.evidence_ids == (
        "EV-001",
        "EV-002",
        "EV-003",
    )
    assert signal.evidence_count == 3


def test_decision_to_asset_signal_preserves_thesis_exit_losslessly():
    from iip.integration.decision_adapter import decision_to_asset_signal

    thesis_exit = _thesis_exit()

    signal = decision_to_asset_signal(
        _decision(thesis_exit=thesis_exit),
        _portfolio_asset(),
    )

    assert signal.thesis_exit_state == ThesisExitState.REVIEW.value
    assert signal.thesis_exit_failed_gates == ()
    assert signal.thesis_exit_attention_gates == (
        "valuation",
        "opportunity_cost",
    )
    assert signal.thesis_exit_unknown_gates == ()
    assert signal.thesis_exit_critical_failure is False


def test_break_does_not_artificially_change_decision_action():
    from iip.integration.decision_adapter import decision_to_asset_signal

    thesis_exit = ThesisExitAssessment(
        fundamentals=GateStatus.FAIL,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.PASS,
        dividends=GateStatus.PASS,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.PASS,
        state=ThesisExitState.BREAK,
        failed_gates=("fundamentals",),
        attention_gates=(),
        unknown_gates=(),
        critical_failure=True,
    )

    signal = decision_to_asset_signal(
        _decision(
            verdict=Verdict.MANTER,
            thesis_exit=thesis_exit,
        ),
        _portfolio_asset(),
    )

    assert signal.action is Action.MANTER
    assert signal.thesis_exit_state == ThesisExitState.BREAK.value
    assert signal.thesis_exit_critical_failure is True


def test_decision_without_evidence_remains_valid_projection():
    from iip.integration.decision_adapter import decision_to_asset_signal

    signal = decision_to_asset_signal(
        _decision(evidence=()),
        _portfolio_asset(),
    )

    assert signal.evidence_ids == ()
    assert signal.evidence_count == 0


def test_decision_without_thesis_exit_remains_backward_compatible():
    from iip.integration.decision_adapter import decision_to_asset_signal

    signal = decision_to_asset_signal(
        _decision(thesis_exit=None),
        _portfolio_asset(),
    )

    assert signal.thesis_exit_state is None
    assert signal.thesis_exit_failed_gates == ()
    assert signal.thesis_exit_attention_gates == ()
    assert signal.thesis_exit_unknown_gates == ()
    assert signal.thesis_exit_critical_failure is None


def test_projection_uses_registry_asset_class_not_decision_field():
    from iip.integration.decision_adapter import decision_to_asset_signal

    signal = decision_to_asset_signal(
        _decision(),
        _portfolio_asset(asset_class="equity"),
    )

    assert signal.asset_class == "equity"
    assert not hasattr(_decision(), "asset_class")
