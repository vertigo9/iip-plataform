from datetime import UTC, datetime

from iip.atlas.knowledge_adapter import AtlasKnowledgeAdapter
from iip.atlas.models import AtlasDocument


def make_document():
    return AtlasDocument(
        document_id="xp_asset:XPML11:2026:abcdef1234567890",
        ticker="XPML11",
        provider="xp_asset",
        role="institutional_primary",
        url="https://www.xpasset.com.br/fundos/xp-malls/",
        final_url="https://www.xpasset.com.br/fundos/xp-malls/",
        content_type="application/pdf",
        status_code=200,
        body=b"%PDF-XPML11",
        content_hash="abcdef1234567890",
        discovered_year=2026,
        ingested_at=datetime(2026, 8, 29, tzinfo=UTC),
    )


def test_semantic_knowledge_id_is_preserved():
    evidence = AtlasKnowledgeAdapter.to_evidence(make_document())
    assert evidence.evidence_id == "xp_asset:XPML11:2026:abcdef1234567890"


def test_original_document_id_remains_traceable():
    evidence = AtlasKnowledgeAdapter.to_evidence(make_document())
    assert (
        "document_id=xp_asset:XPML11:2026:abcdef1234567890" in evidence.relevant_facts
    )
