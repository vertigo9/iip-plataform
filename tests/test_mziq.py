import json

import pytest

from iip.sources.mziq import (
    build_documents_target,
    build_years_target,
    parse_documents_response,
    parse_years_response,
)

COMPANY_ID = "6298ef6f-2b75-43f8-b2ab-99e3fe33e809"
CATEGORIES = (
    "central-resultados-earnings-release",
    "central-resultados-dfp",
    "central-resultados-teleconferencia",
)


def test_build_years_target_formats_url_and_body():
    target = build_years_target(COMPANY_ID, CATEGORIES)

    assert target.url == (
        f"https://apicatalog.mziq.com/filemanager/company/{COMPANY_ID}"
        "/categoryInternalName/document/language/years"
    )
    assert target.body == {
        "categoryInternalNames": list(CATEGORIES),
        "language_code": "pt_BR",
    }


def test_build_years_target_rejects_empty_company_id():
    with pytest.raises(ValueError):
        build_years_target("", CATEGORIES)


def test_build_years_target_rejects_empty_categories():
    with pytest.raises(ValueError):
        build_years_target(COMPANY_ID, ())


def test_build_documents_target_formats_url_and_body():
    target = build_documents_target(COMPANY_ID, 2026, CATEGORIES)

    assert target.url == (
        f"https://apicatalog.mziq.com/filemanager/company/{COMPANY_ID}"
        "/filter/categories/year/meta"
    )
    assert target.body == {
        "year": "2026",
        "categories": list(CATEGORIES),
        "language": "pt_BR",
        "published": True,
    }


def test_build_documents_target_rejects_empty_company_id():
    with pytest.raises(ValueError):
        build_documents_target("", 2026, CATEGORIES)


def test_build_documents_target_rejects_empty_categories():
    with pytest.raises(ValueError):
        build_documents_target(COMPANY_ID, 2026, ())


# --- real captured response fragments (ABCB4, confirmed live) ---

YEARS_RESPONSE = json.dumps({"success": True, "data": [2026, 2025, 2024, 2023]}).encode(
    "utf-8"
)

YEARS_RESPONSE_FAILURE = json.dumps({"success": False}).encode("utf-8")

# One normal document (file_url present) + one video/audio item where
# file_url is null and the real URL is only in link_url — this exact
# gap was found in the live capture, not invented.
DOCUMENTS_RESPONSE = json.dumps(
    {
        "success": True,
        "data": {
            "document_metas": [
                {
                    "id": "5ff5f45c-517a-4c84-9654-b2d5b68f8047",
                    "company_id": COMPANY_ID,
                    "file_name_original": "DFP 2T26",
                    "file_url": (
                        "https://api.mziq.com/mzfilemanager/v2/d/"
                        f"{COMPANY_ID}/5e68483b-ad5d-2fc3-e4ca-cfc970bfed31?origin=2"
                    ),
                    "file_size": "1599137",
                    "file_date": "2026-08-06T00:00:00.000Z",
                    "file_quarter": 2,
                    "file_year": 2026,
                    "link_url": None,
                    "language_code": "pt_BR",
                    "is_published": True,
                    "file_published_date": "2026-08-06T00:00:00.000Z",
                    "file_title": "DFP 2T26 PT",
                    "download_link_id": "5e68483b-ad5d-2fc3-e4ca-cfc970bfed31",
                    "internal_name": "central-resultados-dfp",
                    "cached_at": "2026-09-10T04:27:49.543Z",
                    "permalink": (
                        "https://api.mziq.com/mzfilemanager/v2/d/"
                        f"{COMPANY_ID}/5e68483b-ad5d-2fc3-e4ca-cfc970bfed31?origin=2"
                    ),
                },
                {
                    "id": "9017a7ba-e32a-4751-a460-edbe3ed9db81",
                    "company_id": COMPANY_ID,
                    "file_name_original": "Conferência 2T26 - Áudio e Vídeo",
                    "file_url": None,
                    "file_size": "0",
                    "file_date": "2026-08-07T00:00:00.000Z",
                    "file_quarter": 2,
                    "file_year": 2026,
                    "link_url": (
                        "https://api.mziq.com/mzfilemanager/v2/d/"
                        f"{COMPANY_ID}/e9854239-8d03-fd71-c5f6-8cc4f9f2beda?origin=2"
                    ),
                    "language_code": "pt_BR",
                    "is_published": True,
                    "file_published_date": "2026-08-07T00:00:00.000Z",
                    "file_title": "Conferência 2T26 - Áudio e Vídeo",
                    "download_link_id": "e9854239-8d03-fd71-c5f6-8cc4f9f2beda",
                    "internal_name": "central-resultados-teleconferencia",
                    "cached_at": "2026-09-10T04:27:49.543Z",
                    "permalink": (
                        "https://api.mziq.com/mzfilemanager/v2/d/"
                        f"{COMPANY_ID}/e9854239-8d03-fd71-c5f6-8cc4f9f2beda?origin=2"
                    ),
                },
            ]
        },
    }
).encode("utf-8")


def test_parse_years_response_extracts_list():
    assert parse_years_response(YEARS_RESPONSE) == (2026, 2025, 2024, 2023)


def test_parse_years_response_returns_empty_on_failure():
    assert parse_years_response(YEARS_RESPONSE_FAILURE) == ()


def test_parse_documents_response_extracts_normal_document():
    docs = parse_documents_response(DOCUMENTS_RESPONSE)
    dfp = next(d for d in docs if d.category == "central-resultados-dfp")

    assert dfp.file_title == "DFP 2T26 PT"
    assert dfp.file_year == 2026
    assert dfp.file_quarter == 2
    assert dfp.file_size == 1599137
    assert dfp.url == (
        f"https://api.mziq.com/mzfilemanager/v2/d/{COMPANY_ID}/"
        "5e68483b-ad5d-2fc3-e4ca-cfc970bfed31?origin=2"
    )


def test_parse_documents_response_falls_back_to_link_url_when_file_url_is_null():
    # This is the real gap found live: video/audio items have
    # file_url=None and the actual URL only in link_url.
    docs = parse_documents_response(DOCUMENTS_RESPONSE)
    conferencia = next(
        d for d in docs if d.category == "central-resultados-teleconferencia"
    )

    assert conferencia.url == (
        f"https://api.mziq.com/mzfilemanager/v2/d/{COMPANY_ID}/"
        "e9854239-8d03-fd71-c5f6-8cc4f9f2beda?origin=2"
    )


def test_parse_documents_response_returns_empty_on_failure():
    body = json.dumps({"success": False}).encode("utf-8")
    assert parse_documents_response(body) == ()


def test_parse_documents_response_handles_empty_document_metas():
    body = json.dumps({"success": True, "data": {"document_metas": []}}).encode("utf-8")
    assert parse_documents_response(body) == ()


def test_parse_documents_response_treats_missing_file_size_as_none():
    item = json.loads(DOCUMENTS_RESPONSE)
    item["data"]["document_metas"][1]["file_size"] = None
    docs = parse_documents_response(json.dumps(item).encode("utf-8"))
    conferencia = next(
        d for d in docs if d.category == "central-resultados-teleconferencia"
    )
    assert conferencia.file_size is None


def test_parse_documents_response_treats_garbage_file_size_as_none():
    item = json.loads(DOCUMENTS_RESPONSE)
    item["data"]["document_metas"][0]["file_size"] = "n/a"
    docs = parse_documents_response(json.dumps(item).encode("utf-8"))
    dfp = next(d for d in docs if d.category == "central-resultados-dfp")
    assert dfp.file_size is None
