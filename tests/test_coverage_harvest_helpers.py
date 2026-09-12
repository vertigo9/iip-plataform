from iip.harvest.patria import (
    Document,
    _documents_from_mziq_meta,
    _extract_document_meta,
    _hash_file,
    _parse_years,
    _replace_year_in_payload,
    _resolve_real_extension,
    _safe_name,
)


def test_extension_resolution():
    assert (
        _resolve_real_extension(
            {"content-disposition": 'attachment; filename="report.PDF"'},
            "https://x.invalid/file",
        )
        == ".pdf"
    )
    assert (
        _resolve_real_extension(
            {
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            },
            "https://x.invalid/file",
        )
        == ".xlsx"
    )
    assert _resolve_real_extension({}, "https://x.invalid/file") == ""


def test_safe_name_hash_and_year_parser(tmp_path):
    assert _safe_name("  P@tria / CPFE3 !!  ") == "P tria CPFE3"
    path = tmp_path / "x.bin"
    path.write_bytes(b"abc")
    assert len(_hash_file(path)) == 64
    assert list(_parse_years("2024")) == [2024]
    assert list(_parse_years("2022-2024")) == [2022, 2023, 2024]


def test_replace_year_json_and_fallback():
    payload = '{"year":2024,"nested":{"date":"2024"},"other":2020}'
    result = _replace_year_in_payload(payload, 2026)
    assert '"year":2026' in result
    assert '"date":"2026"' in result
    assert '"other":2026' in result

    fallback = "year=2024;old=2020"
    assert _replace_year_in_payload(fallback, 2026) == "year=2026;old=2026"


def test_extract_meta_nested_and_document_mapping():
    payload = {
        "data": {
            "document_meta": [
                {
                    "file_year": 2026,
                    "file_url": "u1",
                    "file_name": "A.pdf",
                    "category": "RMG",
                },
                {"file_year": "bad", "downloadUrl": "u2", "title": "B.pdf"},
            ]
        },
        "document_metas": [{"file_year": 2025, "file_url": "old"}],
    }
    meta = _extract_document_meta(payload)
    assert len(meta) == 3

    docs = _documents_from_mziq_meta(
        [
            {
                "file_year": 2026,
                "file_url": "u1",
                "file_name": "A.pdf",
                "category": "RMG",
            },
            {"file_year": 2025, "file_url": "old"},
            {"file_year": "bad", "downloadUrl": "u2", "title": "B.pdf"},
            {"file_year": 2026, "file_url": "u1"},
            {"file_year": 2026, "file_url": ""},
        ],
        "CPFE3",
        2026,
    )
    assert [d.url for d in docs] == ["u1", "u2"]
    assert docs[0].title == "A.pdf"
    assert docs[0].category == "RMG"


def test_document_is_immutable():
    doc = Document("CPFE3", 2026, "RMG", "x", "u")
    assert doc.sha256 is None
    try:
        doc.title = "changed"
    except Exception:  # noqa: S110,BLE001 — teste verifica que o objeto e imutavel; qualquer excecao confirma isso
        pass
    else:
        raise AssertionError("Document must be frozen")
