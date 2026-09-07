from iip.harvest.patria import (
    Document,
    _documents_from_mziq_meta,
    _extract_document_meta,
    _replace_year_in_payload,
    _resolve_real_extension,
    _safe_name,
)


def test_resolve_real_extension_from_content_type():
    assert (
        _resolve_real_extension(
            {"content-type": "application/pdf; charset=binary"},
            "https://example.test/abc",
        )
        == ".pdf"
    )


def test_resolve_real_extension_from_content_disposition():
    assert (
        _resolve_real_extension(
            {
                "content-type": "application/octet-stream",
                "content-disposition": 'attachment; filename="relatorio.xlsx"',
            },
            "https://example.test/abc",
        )
        == ".xlsx"
    )


def test_resolve_real_extension_from_utf8_content_disposition():
    assert (
        _resolve_real_extension(
            {
                "content-disposition": "attachment; filename*=UTF-8''relatorio%20final.pdf",
            },
            "https://example.test/abc",
        )
        == ".pdf"
    )


def test_resolve_real_extension_unknown_returns_empty():
    assert (
        _resolve_real_extension(
            {"content-type": "application/octet-stream"},
            "https://example.test/abc",
        )
        == ""
    )


def test_replace_year_in_json():
    payload = '{"year": 2023, "label": "2023", "name": "document"}'

    result = _replace_year_in_payload(payload, 2024)

    assert '"year":2024' in result
    assert '"label":"2024"' in result


def test_replace_year_in_nested_json():
    payload = {
        "filters": {
            "year": 2022,
            "nested": ["2022", 2021, "unchanged"],
        }
    }

    import json

    result = json.loads(_replace_year_in_payload(json.dumps(payload), 2025))

    assert result["filters"]["year"] == 2025
    assert result["filters"]["nested"] == ["2025", 2025, "unchanged"]


def test_replace_year_in_non_json_payload():
    payload = "year=2021&from=2021&to=2022"

    result = _replace_year_in_payload(payload, 2026)

    assert result == "year=2026&from=2026&to=2026"


def test_replace_year_empty_payload():
    assert _replace_year_in_payload("", 2025) == ""


def test_extract_document_meta_nested():
    payload = {
        "data": {
            "document_metas": [
                {"file_year": 2024, "file_url": "https://example/a.pdf"},
                {"file_year": 2023, "file_url": "https://example/b.pdf"},
            ]
        },
        "other": {
            "document_meta": [
                {"file_year": 2024, "file_url": "https://example/c.pdf"},
            ]
        },
    }

    result = _extract_document_meta(payload)

    assert len(result) == 3
    assert result[0]["file_year"] == 2024


def test_extract_document_meta_from_list():
    payload = [
        {"document_meta": [{"file_url": "https://example/a.pdf"}]},
        {"document_metas": [{"file_url": "https://example/b.pdf"}]},
    ]

    result = _extract_document_meta(payload)

    assert len(result) == 2


def test_extract_document_meta_without_meta():
    assert _extract_document_meta({"data": {"items": []}}) == []


def test_documents_from_mziq_meta_filters_year():
    meta = [
        {
            "file_year": 2024,
            "file_url": "https://example/a.pdf",
            "file_name_original": "Relatorio 2024.pdf",
            "category_name": "Relatórios",
        },
        {
            "file_year": 2023,
            "file_url": "https://example/b.pdf",
            "file_name_original": "Relatorio 2023.pdf",
            "category_name": "Relatórios",
        },
    ]

    docs = _documents_from_mziq_meta(meta, "ABCD3", 2024)

    assert len(docs) == 1
    assert docs[0].ticker == "ABCD3"
    assert docs[0].year == 2024
    assert docs[0].title == "Relatorio 2024.pdf"
    assert docs[0].category == "Relatórios"


def test_documents_from_mziq_meta_accepts_url_variants():
    meta = [
        {
            "file_year": 2024,
            "fileUrl": "https://example/a.pdf",
            "file_title": "A",
        },
        {
            "file_year": 2024,
            "download_url": "https://example/b.pdf",
            "file_name": "B",
        },
        {
            "file_year": 2024,
            "linkUrl": "https://example/c.pdf",
            "title": "C",
        },
    ]

    docs = _documents_from_mziq_meta(meta, "TEST3", 2024)

    assert len(docs) == 3
    assert [doc.title for doc in docs] == ["A", "B", "C"]


def test_documents_from_mziq_meta_deduplicates_urls():
    meta = [
        {
            "file_year": 2024,
            "file_url": "https://example/a.pdf",
            "file_name_original": "A",
        },
        {
            "file_year": 2024,
            "file_url": "https://example/a.pdf",
            "file_name_original": "A duplicate",
        },
    ]

    docs = _documents_from_mziq_meta(meta, "TEST3", 2024)

    assert len(docs) == 1


def test_documents_from_mziq_meta_defaults_category():
    meta = [
        {
            "file_year": 2024,
            "file_url": "https://example/a.pdf",
            "file_name_original": "A",
        }
    ]

    docs = _documents_from_mziq_meta(meta, "TEST3", 2024)

    assert docs[0].category == "Outros"


def test_documents_from_mziq_meta_skips_missing_url():
    meta = [
        {
            "file_year": 2024,
            "file_name_original": "sem URL",
        }
    ]

    assert _documents_from_mziq_meta(meta, "TEST3", 2024) == []


def test_safe_name_removes_unsafe_characters():
    result = _safe_name('Relatório: 2024 / "Final"')

    assert ":" not in result
    assert "/" not in result
    assert '"' not in result
    assert "Relatório" in result


def test_safe_name_collapses_whitespace():
    assert _safe_name("  um   dois    três  ") == "um dois três"


def test_document_is_constructed():
    doc = Document(
        ticker="TEST3",
        year=2024,
        category="Relatórios",
        title="Teste.pdf",
        url="https://example.test/test.pdf",
    )

    assert doc.ticker == "TEST3"
    assert doc.year == 2024
