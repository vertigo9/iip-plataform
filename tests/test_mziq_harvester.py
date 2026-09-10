import json

from iip.sources.mziq import build_documents_target, build_years_target
from iip.sources.mziq_harvester import MziqHTTPHarvester

COMPANY_ID = "6298ef6f-2b75-43f8-b2ab-99e3fe33e809"
CATEGORIES = ("central-resultados-earnings-release",)


class FakeYearsResponse:
    status = 200

    def read(self):
        return json.dumps({"success": True, "data": [2026, 2025]}).encode("utf-8")


class FakeDocumentsResponse:
    status = 200

    def read(self):
        return json.dumps(
            {
                "success": True,
                "data": {
                    "document_metas": [
                        {
                            "id": "abc",
                            "company_id": COMPANY_ID,
                            "file_name_original": "ER 2T26",
                            "file_url": "https://api.mziq.com/mzfilemanager/v2/d/x/y",
                            "file_size": "100",
                            "file_date": "2026-08-06T00:00:00.000Z",
                            "file_quarter": 2,
                            "file_year": 2026,
                            "link_url": None,
                            "file_title": "ER 2T26",
                            "internal_name": "central-resultados-earnings-release",
                            "is_published": True,
                        }
                    ]
                },
            }
        ).encode("utf-8")


def test_fetch_years_sends_post_with_json_body():
    captured = {}

    def opener(request, timeout):
        captured["method"] = request.get_method()
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeYearsResponse()

    harvester = MziqHTTPHarvester(opener=opener)
    years = harvester.fetch_years(build_years_target(COMPANY_ID, CATEGORIES))

    assert years == (2026, 2025)
    assert captured["method"] == "POST"
    assert captured["headers"]["Content-type"] == "application/json"
    assert captured["body"]["categoryInternalNames"] == list(CATEGORIES)


def test_fetch_documents_sends_post_with_json_body():
    captured = {}

    def opener(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeDocumentsResponse()

    harvester = MziqHTTPHarvester(opener=opener)
    docs = harvester.fetch_documents(
        build_documents_target(COMPANY_ID, 2026, CATEGORIES)
    )

    assert len(docs) == 1
    assert docs[0].file_title == "ER 2T26"
    assert captured["body"]["year"] == "2026"


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return json.dumps({"success": True, "data": []}).encode("utf-8")

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = MziqHTTPHarvester(opener=opener)
    years = harvester.fetch_years(build_years_target(COMPANY_ID, CATEGORIES))
    assert years == ()
