from types import SimpleNamespace

from iip.atlas import AtlasDocument, AtlasDocumentAdapter


def make_fetched(
    *,
    ticker="XPML11",
    provider="XP_ASSET",
    role="Institutional_Primary",
    year=2026,
    content_type="text/html; charset=utf-8",
    body=b"<html>XPML11</html>",
    final_url="https://www.xpasset.com.br/fundos/xp-malls/",
):
    target = SimpleNamespace(
        ticker=ticker,
        provider=provider,
        role=role,
        url="https://www.xpasset.com.br/fundos/xp-malls/",
        year=year,
    )
    return SimpleNamespace(
        target=target,
        status_code=200,
        content_type=content_type,
        body=body,
        final_url=final_url,
    )


def test_import_and_build():
    document = AtlasDocumentAdapter().from_fetched(make_fetched())

    assert isinstance(document, AtlasDocument)
    assert document.ticker == "XPML11"
    assert document.provider == "xp_asset"
    assert document.role == "institutional_primary"
    assert document.content_type == "text/html"
    assert document.status_code == 200


def test_hash_and_document_id_are_deterministic():
    first = AtlasDocumentAdapter().from_fetched(make_fetched())
    second = AtlasDocumentAdapter().from_fetched(make_fetched())

    assert first.content_hash == second.content_hash
    assert first.document_id == second.document_id


def test_body_change_changes_identity():
    first = AtlasDocumentAdapter().from_fetched(make_fetched(body=b"A"))
    second = AtlasDocumentAdapter().from_fetched(make_fetched(body=b"B"))

    assert first.content_hash != second.content_hash
    assert first.document_id != second.document_id


def test_year_participates_in_identity():
    first = AtlasDocumentAdapter().from_fetched(make_fetched(year=2025))
    second = AtlasDocumentAdapter().from_fetched(make_fetched(year=2026))

    assert first.document_id != second.document_id


def test_final_url_falls_back_to_target():
    document = AtlasDocumentAdapter().from_fetched(make_fetched(final_url=""))

    assert document.final_url == document.url


def test_fields_are_normalized():
    document = AtlasDocumentAdapter().from_fetched(
        make_fetched(
            ticker=" xpml11 ",
            provider=" XP_ASSET ",
            role=" REGULATORY ",
            content_type=" APPLICATION/PDF ; charset=binary ",
        )
    )

    assert document.ticker == "XPML11"
    assert document.provider == "xp_asset"
    assert document.role == "regulatory"
    assert document.content_type == "application/pdf"


def test_ingestion_timestamp_is_utc_aware():
    document = AtlasDocumentAdapter().from_fetched(make_fetched())

    assert document.ingested_at.tzinfo is not None
    assert document.ingested_at.utcoffset() is not None
