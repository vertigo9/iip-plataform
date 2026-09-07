from datetime import UTC, datetime
from types import SimpleNamespace

from iip.atlas.batch import HistoricalAtlasIngestion
from iip.atlas.history import AtlasHistoryProcessor, HistoryBatch
from iip.atlas.models import AtlasDocument


def document(year=2026, content=b"same", document_id=None):
    return AtlasDocument(
        document_id=document_id or f"xp_asset:XPML11:{year}:{content.hex()[:16]}",
        ticker="XPML11",
        provider="xp_asset",
        role="institutional_primary",
        url="https://www.xpasset.com.br/fundos/xp-malls/",
        final_url="https://www.xpasset.com.br/fundos/xp-malls/",
        content_type="application/pdf",
        status_code=200,
        body=content,
        content_hash=content.hex(),
        discovered_year=year,
        ingested_at=datetime(2026, 8, 29, tzinfo=UTC),
    )


def test_history_keeps_distinct_years():
    result = AtlasHistoryProcessor.process(
        (document(2024), document(2025), document(2026))
    )

    assert len(result.documents) == 3
    assert result.duplicates == ()
    assert result.years == (2024, 2025, 2026)


def test_history_deduplicates_only_equal_document_ids():
    first = document(2026, b"A")
    repeated = document(2026, b"B", document_id=first.document_id)
    result = AtlasHistoryProcessor.process((first, repeated))

    assert result.documents == (first,)
    assert result.duplicates == (repeated,)


def test_same_content_different_year_is_not_duplicate():
    result = AtlasHistoryProcessor.process((document(2025, b"A"), document(2026, b"A")))

    assert len(result.documents) == 2
    assert result.duplicates == ()


def test_duplicate_order_is_preserved():
    first = document(2026, b"A")
    second = document(2026, b"B")
    result = AtlasHistoryProcessor.process((first, second, first, second))

    assert result.documents == (first, second)
    assert result.duplicates == (first, second)


def test_empty_history_is_valid():
    result = AtlasHistoryProcessor.process(())

    assert isinstance(result, HistoryBatch)
    assert result.documents == ()
    assert result.duplicates == ()
    assert result.years == ()


def test_historical_ingestion_wraps_existing_report():
    atlas_report = SimpleNamespace(
        documents=(document(2024), document(2025), document(2026))
    )

    class FakePipeline:
        def ingest(self, asset, years):
            return atlas_report

    wrapper = HistoricalAtlasIngestion(FakePipeline())
    result = wrapper.ingest(object(), range(2024, 2027))

    assert result.report is atlas_report
    assert result.history.documents == atlas_report.documents
    assert result.history.years == (2024, 2025, 2026)
