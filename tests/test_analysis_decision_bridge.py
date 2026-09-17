from iip.analysis import AssetData, FIIAnalyzer
from iip.decision.analysis_bridge import analysis_to_intelligence_input
from iip.decision.decision_engine import decide
from iip.decision.models import EvidenceRef


def make_report(dividend_yield=5.0):
    data = AssetData(
        symbol="BTLG11",
        sector="Logística",
        industry="Galpões",
        price=99.88,
        financials={"dividend_yield": dividend_yield, "occupancy_rate": 0.85},
    )
    return FIIAnalyzer().analyze(data)


def test_bridge_converts_scores_from_0_100_to_0_10_scale():
    report = make_report()
    intelligence_input, _ = analysis_to_intelligence_input(
        report, thesis_signal="reforco", evidence=(EvidenceRef("EV-1"),)
    )

    assert 0 <= intelligence_input.dividend_score <= 10
    assert 0 <= intelligence_input.quality_score <= 10
    assert 0 <= intelligence_input.opportunity_score <= 10
    assert intelligence_input.opportunity_score == round(report.overall_score / 10, 2)


def test_bridge_maps_risk_level_to_portuguese_values(monkeypatch):
    report = make_report()
    intelligence_input, warnings = analysis_to_intelligence_input(
        report, thesis_signal="reforco", evidence=(EvidenceRef("EV-1"),)
    )

    assert intelligence_input.risk_level in ("Baixo", "Médio", "Alto")
    assert not any("não reconhecido" in w for w in warnings)


def test_bridge_warns_and_defaults_to_neutral_when_valuation_score_omitted():
    report = make_report()
    intelligence_input, warnings = analysis_to_intelligence_input(
        report, thesis_signal="reforco", evidence=(EvidenceRef("EV-1"),)
    )

    assert intelligence_input.valuation_score == 5.0
    assert any("valuation_score não fornecido" in w for w in warnings)


def test_bridge_uses_explicit_valuation_score_without_warning_when_given():
    report = make_report()
    intelligence_input, warnings = analysis_to_intelligence_input(
        report,
        thesis_signal="reforco",
        evidence=(EvidenceRef("EV-1"),),
        valuation_score=8.0,
    )

    assert intelligence_input.valuation_score == 8.0
    assert not any("valuation_score não fornecido" in w for w in warnings)


def test_bridge_never_derives_valuation_from_another_pillar():
    # Garante que nao existe nenhum caminho que faz valuation_score
    # emprestar o valor de outro pilar quando omitido -- deve ser
    # sempre o neutro fixo, nunca opportunity/quality/dividend.
    report_alto = make_report(dividend_yield=15.0)
    report_baixo = make_report(dividend_yield=0.5)

    input_alto, _ = analysis_to_intelligence_input(
        report_alto, thesis_signal="reforco", evidence=(EvidenceRef("EV-1"),)
    )
    input_baixo, _ = analysis_to_intelligence_input(
        report_baixo, thesis_signal="reforco", evidence=(EvidenceRef("EV-1"),)
    )

    assert input_alto.valuation_score == input_baixo.valuation_score == 5.0


def test_bridge_output_is_directly_usable_by_decide():
    report = make_report()
    intelligence_input, _ = analysis_to_intelligence_input(
        report, thesis_signal="reforco", evidence=(EvidenceRef("EV-1"),)
    )

    decision = decide(intelligence_input)

    assert decision.ticker == "BTLG11"
    assert decision.score >= 0
    # Thesis Exit is part of the current Decision contract: when present,
    # the engine appends three diagnostic reasons to the four legacy reasons.
    assert len(decision.reasons) == 7
    assert decision.reasons[0].startswith("composite_score=")
    assert decision.reasons[1].startswith("confidence=")
    assert decision.reasons[2] == "thesis=reforco"
    assert decision.reasons[3].startswith("risk=")
    assert decision.reasons[4].startswith("thesis_exit=")
    assert decision.reasons[5].startswith("thesis_exit_failed=")
    assert decision.reasons[6].startswith("thesis_exit_attention=")


def test_bridge_ticker_matches_report_symbol():
    report = make_report()
    intelligence_input, _ = analysis_to_intelligence_input(
        report, thesis_signal="reforco", evidence=(EvidenceRef("EV-1"),)
    )
    assert intelligence_input.ticker == report.asset_symbol
def test_bridge_populates_thesis_exit():
    report = make_report()

    intelligence_input, _ = analysis_to_intelligence_input(
        report,
        thesis_signal="reforco",
        evidence=(EvidenceRef("EV-1"),),
    )

    assert intelligence_input.thesis_exit is not None
    
def test_bridge_thesis_exit_is_semantic_assessment():
    from iip.decision.thesis_exit_gate import ThesisExitAssessment

    report = make_report()

    intelligence_input, _ = analysis_to_intelligence_input(
        report,
        thesis_signal="reforco",
        evidence=(EvidenceRef("EV-1"),),
    )

    assert isinstance(intelligence_input.thesis_exit, ThesisExitAssessment)