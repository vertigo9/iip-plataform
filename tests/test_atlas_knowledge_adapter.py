from __future__ import annotations

from datetime import UTC, datetime

from iip.atlas import AtlasDocument, AtlasKnowledgeAdapter


def make_document(year: int | None = 2026) -> AtlasDocument:
    return AtlasDocument(
        document_id="xp_asset:XPML11:2026:abcdef1234567890",
        ticker="XPML11",
        provider="xp_asset",
        role="institutional_primary",
        url="https://www.xpasset.com.br/fundos/xp-malls/",
        final_url="https://www.xpasset.com.br/fundos/xp-malls/",
        content_type="application/pdf",
        status_code=200,
        body=b"%PDF-xpml11",
        content_hash="abcdef1234567890",
        discovered_year=year,
        ingested_at=datetime(2026, 8, 29, tzinfo=UTC),
    )


class FakeBridge:
    def __init__(self, persisted=None):
        self.persisted = persisted
        self.items = []

    def persist_evidence(self, evidence):
        self.items.append(evidence)
        return self.persisted


def test_to_evidence_maps_canonical_fields():
    evidence = AtlasKnowledgeAdapter.to_evidence(make_document())

    assert evidence.evidence_id == "xp_asset:XPML11:2026:abcdef1234567890"
    assert evidence.ticker == "XPML11"
    assert evidence.date.year == 2026
    assert evidence.date.month == 12
    assert evidence.date.day == 31
    assert evidence.source_type == "atlas"
    assert evidence.source_url.endswith("/xp-malls/")
    assert evidence.document_hash == "abcdef1234567890"


def test_to_evidence_contains_traceable_facts():
    evidence = AtlasKnowledgeAdapter.to_evidence(make_document())

    assert "provider=xp_asset" in evidence.relevant_facts
    assert "role=institutional_primary" in evidence.relevant_facts
    assert "content_type=application/pdf" in evidence.relevant_facts
    assert "status_code=200" in evidence.relevant_facts


def test_persist_uses_legacy_bridge_contract():
    bridge = FakeBridge()
    adapter = AtlasKnowledgeAdapter(bridge)

    result = adapter.persist(make_document())

    assert len(bridge.items) == 1
    assert result is bridge.items[0]


def test_persist_returns_bridge_result_when_available():
    stored = object()
    bridge = FakeBridge(persisted=stored)

    result = AtlasKnowledgeAdapter(bridge).persist(make_document())

    assert result is stored


class ProjectingBridge(FakeBridge):
    def __init__(self):
        super().__init__()
        self.projected = []

    def sync_evidence_projection(self, evidence):
        self.projected.append(evidence)
        return {"status": "CREATED", "evidence_id": evidence.evidence_id}


def test_persist_uses_projection_when_bridge_supports_it():
    bridge = ProjectingBridge()

    result = AtlasKnowledgeAdapter(bridge).persist(make_document())

    assert result["status"] == "CREATED"
    assert len(bridge.items) == 1
    assert bridge.projected[0] is bridge.items[0]


def test_persist_many_preserves_order():
    bridge = FakeBridge()
    documents = (
        make_document(2024),
        make_document(2025),
        make_document(2026),
    )

    result = AtlasKnowledgeAdapter(bridge).persist_many(documents)

    assert [item.date.year for item in result] == [2024, 2025, 2026]
    assert [item.ticker for item in bridge.items] == ["XPML11", "XPML11", "XPML11"]


def test_missing_discovered_year_uses_ingestion_date():
    document = make_document(None)

    evidence = AtlasKnowledgeAdapter.to_evidence(document)

    assert evidence.date == document.ingested_at.date()


def test_document_is_not_modified():
    document = make_document()
    before = document

    AtlasKnowledgeAdapter.to_evidence(document)

    assert document == before
