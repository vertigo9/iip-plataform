from datetime import date

import pytest

from iip.decision.knowledge_bridge import to_knowledge_decision, to_knowledge_verdict
from iip.decision.models import Decision as EngineDecision
from iip.decision.models import EvidenceRef
from iip.decision.models import Verdict as EngineVerdict
from iip.decision.thesis_exit_gate import (
    GateStatus,
    ThesisExitState,
    assess_thesis_exit,
)
from iip.knowledge.models import DecisionChange
from iip.knowledge.models import Verdict as KnowledgeVerdict


def make_engine_decision(**overrides) -> EngineDecision:
    data = {
        "ticker": "pcip11",
        "verdict": EngineVerdict.COMPRAR,
        "score": 8.7,
        "confidence": 0.9,
        "reasons": ("composite_score=8.70",),
        "evidence": (EvidenceRef("EV-PCIP11-001"),),
    }
    data.update(overrides)
    return EngineDecision(**data)


@pytest.mark.parametrize(
    ("engine_verdict", "expected"),
    [
        (EngineVerdict.COMPRAR, KnowledgeVerdict.COMPRAR),
        (EngineVerdict.MANTER, KnowledgeVerdict.MANTER),
        (EngineVerdict.AGUARDAR, KnowledgeVerdict.AGUARDAR),
        (EngineVerdict.REDUZIR, KnowledgeVerdict.REDUZIR),
        (EngineVerdict.VENDER, KnowledgeVerdict.ENCERRAR),
    ],
)
def test_to_knowledge_verdict_maps_every_engine_value(engine_verdict, expected):
    assert to_knowledge_verdict(engine_verdict) == expected


def test_to_knowledge_decision_uppercases_ticker_and_maps_fields():
    decision = make_engine_decision()

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id="DEC-PCIP11-20260731-001",
        date=date(2026, 7, 31),
    )

    assert knowledge_decision.ticker == "PCIP11"
    assert knowledge_decision.decision_id == "DEC-PCIP11-20260731-001"
    assert knowledge_decision.new_verdict == KnowledgeVerdict.COMPRAR
    assert knowledge_decision.confidence == 0.9
    assert knowledge_decision.evidence_ids == ("EV-PCIP11-001",)
    assert knowledge_decision.reasons == decision.reasons


def test_to_knowledge_decision_defaults_to_no_change_without_previous_verdict():
    decision = make_engine_decision()

    knowledge_decision = to_knowledge_decision(
        decision, decision_id="DEC-001", date=date(2026, 7, 31)
    )

    assert knowledge_decision.previous_verdict is None
    assert knowledge_decision.change_type == DecisionChange.NO_CHANGE


def test_to_knowledge_decision_infers_upgrade():
    decision = make_engine_decision(verdict=EngineVerdict.COMPRAR)

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id="DEC-002",
        date=date(2026, 7, 31),
        previous_verdict=KnowledgeVerdict.AGUARDAR,
    )

    assert knowledge_decision.change_type == DecisionChange.UPGRADE


def test_to_knowledge_decision_infers_downgrade():
    decision = make_engine_decision(verdict=EngineVerdict.REDUZIR)

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id="DEC-003",
        date=date(2026, 7, 31),
        previous_verdict=KnowledgeVerdict.COMPRAR,
    )

    assert knowledge_decision.change_type == DecisionChange.DOWNGRADE


def test_to_knowledge_decision_no_change_when_verdict_repeats():
    decision = make_engine_decision(verdict=EngineVerdict.MANTER)

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id="DEC-004",
        date=date(2026, 7, 31),
        previous_verdict=KnowledgeVerdict.MANTER,
    )

    assert knowledge_decision.change_type == DecisionChange.NO_CHANGE


def test_to_knowledge_decision_explicit_change_type_overrides_inference():
    decision = make_engine_decision(verdict=EngineVerdict.AGUARDAR)

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id="DEC-005",
        date=date(2026, 7, 31),
        previous_verdict=KnowledgeVerdict.COMPRAR,
        change_type=DecisionChange.THESIS_CHANGE,
    )

    assert knowledge_decision.change_type == DecisionChange.THESIS_CHANGE



def make_thesis_exit_assessment():
    return assess_thesis_exit(
        fundamentals=GateStatus.FAIL,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.ATTENTION,
        dividends=GateStatus.ATTENTION,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.UNKNOWN,
    )


def test_to_knowledge_decision_projects_thesis_exit_semantic_fields():
    thesis_exit = make_thesis_exit_assessment()
    decision = make_engine_decision(thesis_exit=thesis_exit)

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id="DEC-PCIP11-THESIS-001",
        date=date(2026, 7, 31),
    )

    assert knowledge_decision.thesis_exit_state == ThesisExitState.BREAK.value
    assert knowledge_decision.thesis_exit_failed_gates == ("fundamentals",)
    assert knowledge_decision.thesis_exit_attention_gates == (
        "valuation",
        "dividends",
    )
    assert knowledge_decision.thesis_exit_unknown_gates == ("opportunity_cost",)
    assert knowledge_decision.thesis_exit_critical_failure is True


def test_to_knowledge_decision_without_thesis_exit_remains_backward_compatible():
    decision = make_engine_decision()

    knowledge_decision = to_knowledge_decision(
        decision,
        decision_id="DEC-PCIP11-NO-THESIS-001",
        date=date(2026, 7, 31),
    )

    assert knowledge_decision.thesis_exit_state is None
    assert knowledge_decision.thesis_exit_failed_gates == ()
    assert knowledge_decision.thesis_exit_attention_gates == ()
    assert knowledge_decision.thesis_exit_unknown_gates == ()
    assert knowledge_decision.thesis_exit_critical_failure is None
