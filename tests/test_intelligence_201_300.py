from datetime import UTC, datetime

from iip.intelligence.credit_intelligence import CreditSnapshot, credit_risk_flags
from iip.intelligence.document_classification import DocumentType, classify_title
from iip.intelligence.document_enrichment import enrich
from iip.intelligence.event_chain import EventChain, EventEdge, EventNode
from iip.intelligence.evidence_chain import EvidenceChain, EvidenceLink
from iip.intelligence.intelligence_pipeline import stage_document
from iip.intelligence.portfolio_intelligence import (
    PositionExposure,
    concentration_alerts,
)
from iip.intelligence.thesis_signal import ThesisSignal, observe


def test_document_classification():
    result = classify_title("d1", "hgru11", "Relatório Gerencial Junho 2026", "patria")
    assert result.document_type == DocumentType.RELATORIO_GERENCIAL
    assert result.ticker == "HGRU11"


def test_document_enrichment_deduplicates_tags():
    result = enrich("d1", "Relatórios", tags=("FII", "FII", "Renda Urbana"))
    assert result.tags == ("FII", "Renda Urbana")


def test_evidence_chain_is_idempotent():
    link = EvidenceLink("e1", "d1", "xp_asset", "https://example", "relatorio")
    chain = EvidenceChain().add(link).add(link)
    assert len(chain.links) == 1


def test_thesis_signal_keeps_evidence():
    obs = observe(
        "XPML11", ThesisSignal.REFORCO, ("e1", "e1"), "Resultado reforçou a tese."
    )
    assert obs.ticker == "XPML11"
    assert obs.evidence_ids == ("e1",)


def test_event_chain_adds_nodes_and_edges():
    first = EventNode("e1", "CDII11", "comunicado", datetime(2026, 1, 1, tzinfo=UTC))
    second = EventNode("e2", "CDII11", "resultado", datetime(2026, 2, 1, tzinfo=UTC))
    chain = (
        EventChain()
        .add_node(first)
        .add_node(second)
        .add_edge(EventEdge("e1", "e2", "precede"))
    )
    assert len(chain.nodes) == 2
    assert chain.edges[0].relation == "precede"


def test_credit_flags():
    snapshot = CreditSnapshot(
        "CDII11", duration_years=6, leverage=2.5, default_flag=True
    )
    assert set(credit_risk_flags(snapshot)) == {
        "default_radar",
        "high_leverage",
        "long_duration",
    }


def test_portfolio_concentration():
    positions = (
        PositionExposure("HGRU11", 0.15, manager="Patria"),
        PositionExposure("LVBI11", 0.10, manager="Patria"),
        PositionExposure("XPML11", 0.08, manager="XP Asset"),
    )
    alerts = concentration_alerts(positions, threshold=0.20)
    assert len(alerts) == 1
    assert alerts[0].value == "Patria"
    assert alerts[0].weight == 0.25


def test_intelligence_pipeline_preserves_lineage():
    result = stage_document(
        "xp:XPML11:2026:1",
        "XPML11",
        "Relatório Gerencial Julho 2026",
        "xp_asset",
        "https://example.test/doc.pdf",
        "Relatórios",
        period="2026-07",
        tags=("FII", "Shopping"),
    )
    assert result.classified.document_type == DocumentType.RELATORIO_GERENCIAL
    assert result.enriched.period == "2026-07"
    assert result.evidence.links[0].provider == "xp_asset"
