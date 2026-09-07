from datetime import UTC

from iip.atlas import AtlasKnowledgeAdapter


def test_existing_evidence_does_not_block_projection():
    class Bridge:
        def __init__(self):
            self.sync_calls = 0

        def persist_evidence(self, evidence):
            raise FileExistsError("append-only")

        def sync_evidence_projection(self, evidence):
            self.sync_calls += 1
            return type(
                "Result", (), {"status": type("Status", (), {"value": "UNCHANGED"})()}
            )()

    from datetime import datetime

    from iip.atlas.models import AtlasDocument

    document = AtlasDocument(
        document_id="xp_asset:XPML11:2026:abcdef",
        ticker="XPML11",
        provider="xp_asset",
        role="institutional_primary",
        url="https://example.com",
        final_url="https://example.com",
        content_type="text/html",
        status_code=200,
        body=b"A",
        content_hash="abcdef",
        discovered_year=2026,
        ingested_at=datetime.now(UTC),
    )

    bridge = Bridge()
    result = AtlasKnowledgeAdapter(bridge).persist(document)

    assert bridge.sync_calls == 1
    assert result.status.value == "UNCHANGED"
