import json

from iip.harvest.patria import (
    Document,
    _api_documents_for_year,
)


class FakeResponse:
    def __init__(self, payload, status=200, ok=True):
        self._payload = payload
        self.status = status
        self.ok = ok

    def json(self):
        return self._payload

    def text(self):
        return json.dumps(self._payload)


class FakeRequest:
    def __init__(self, responses=None, exception=None):
        self.responses = list(responses or [])
        self.exception = exception
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))

        if self.exception is not None:
            raise self.exception

        if self.responses:
            return self.responses.pop(0)

        raise AssertionError("Unexpected request")


class FakeContext:
    def __init__(self, request):
        self.request = request


class FakePage:
    def __init__(self, request):
        self.context = FakeContext(request)


def test_api_documents_for_year_returns_documents():
    payload = {
        "data": {
            "document_metas": [
                {
                    "file_year": 2024,
                    "file_url": "https://api.mziq.com/mzfilemanager/a.pdf",
                    "file_name_original": "Relatorio 2024.pdf",
                    "category_name": "Relatórios",
                }
            ]
        }
    }

    request = FakeRequest([FakeResponse(payload)])
    page = FakePage(request)

    templates = [
        {
            "url": "https://api.mziq.com/filter/categories/year/meta",
            "method": "POST",
            "post_data": '{"year":2023}',
            "headers": {
                "content-type": "application/json",
                "host": "api.mziq.com",
                "connection": "keep-alive",
            },
        }
    ]

    docs = _api_documents_for_year(page, "TEST3", 2024, templates)

    assert len(docs) == 1
    assert isinstance(docs[0], Document)
    assert docs[0].ticker == "TEST3"
    assert docs[0].year == 2024
    assert docs[0].title == "Relatorio 2024.pdf"


def test_api_documents_for_year_replaces_year_in_request():
    payload = {
        "data": {
            "document_metas": [
                {
                    "file_year": 2025,
                    "file_url": "https://api.mziq.com/mzfilemanager/a.pdf",
                }
            ]
        }
    }

    request = FakeRequest([FakeResponse(payload)])
    page = FakePage(request)

    templates = [
        {
            "url": "https://api.mziq.com/filter/categories/year/meta",
            "method": "POST",
            "post_data": '{"year":2023,"nested":{"year":"2023"}}',
            "headers": {
                "content-type": "application/json",
            },
        }
    ]

    docs = _api_documents_for_year(page, "TEST3", 2025, templates)

    assert len(docs) == 1

    assert len(request.calls) == 1

    _, kwargs = request.calls[0]

    assert kwargs["data"] == '{"year":2025,"nested":{"year":"2025"}}'


def test_api_documents_for_year_removes_transport_headers():
    payload = {
        "data": {
            "document_metas": [
                {
                    "file_year": 2024,
                    "file_url": "https://api.mziq.com/mzfilemanager/a.pdf",
                }
            ]
        }
    }

    request = FakeRequest([FakeResponse(payload)])
    page = FakePage(request)

    templates = [
        {
            "url": "https://api.mziq.com/filter/categories/year/meta",
            "method": "POST",
            "post_data": '{"year":2024}',
            "headers": {
                "Content-Type": "application/json",
                "Content-Length": "999",
                "Host": "api.mziq.com",
                "Connection": "keep-alive",
                "Accept-Encoding": "gzip",
                "Authorization": "Bearer test",
            },
        }
    ]

    docs = _api_documents_for_year(page, "TEST3", 2024, templates)

    assert len(docs) == 1

    _, kwargs = request.calls[0]
    headers = kwargs["headers"]

    assert "Content-Length" not in headers
    assert "Host" not in headers
    assert "Connection" not in headers
    assert "Accept-Encoding" not in headers

    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer test"


def test_api_documents_for_year_skips_failed_response():
    request = FakeRequest(
        [
            FakeResponse(
                {"error": "bad request"},
                status=500,
                ok=False,
            ),
            FakeResponse(
                {
                    "data": {
                        "document_metas": [
                            {
                                "file_year": 2024,
                                "file_url": "https://example/a.pdf",
                            }
                        ]
                    }
                }
            ),
        ]
    )

    page = FakePage(request)

    templates = [
        {
            "url": "https://api.example/first",
            "method": "POST",
            "post_data": '{"year":2024}',
            "headers": {},
        },
        {
            "url": "https://api.example/second",
            "method": "POST",
            "post_data": '{"year":2024}',
            "headers": {},
        },
    ]

    docs = _api_documents_for_year(page, "TEST3", 2024, templates)

    assert len(docs) == 1
    assert docs[0].url == "https://example/a.pdf"
    assert len(request.calls) == 2


def test_api_documents_for_year_handles_invalid_json_response():
    class InvalidJsonResponse:
        status = 200
        ok = True

        def json(self):
            raise ValueError("invalid json")

        def text(self):
            return "not-json"

    request = FakeRequest([InvalidJsonResponse()])
    page = FakePage(request)

    templates = [
        {
            "url": "https://api.example/test",
            "method": "POST",
            "post_data='{\"year\":2024}'".replace("post_data=", ""): "",
        }
    ]

    # Replace the intentionally awkward dictionary above with the real template.
    templates = [
        {
            "url": "https://api.example/test",
            "method": "POST",
            "post_data": '{"year":2024}',
            "headers": {},
        }
    ]

    docs = _api_documents_for_year(page, "TEST3", 2024, templates)

    assert docs == []


def test_api_documents_for_year_continues_after_exception():

    request = FakeRequest(exception=RuntimeError("network failure"))

    page = FakePage(request)

    # First template raises; because FakeRequest always raises, this verifies
    # that the function catches the exception and eventually returns [].
    templates = [
        {
            "url": "https://api.example/test",
            "method": "POST",
            "post_data": '{"year":2024}',
            "headers": {},
        }
    ]

    docs = _api_documents_for_year(page, "TEST3", 2024, templates)

    assert docs == []


def test_api_documents_for_year_returns_empty_without_templates():
    request = FakeRequest()
    page = FakePage(request)

    docs = _api_documents_for_year(page, "TEST3", 2024, [])

    assert docs == []
    assert request.calls == []


def test_api_documents_for_year_uses_empty_data_when_no_post_data():
    payload = {
        "data": {
            "document_metas": [
                {
                    "file_year": 2024,
                    "file_url": "https://example/a.pdf",
                }
            ]
        }
    }

    request = FakeRequest([FakeResponse(payload)])
    page = FakePage(request)

    templates = [
        {
            "url": "https://api.example/test",
            "method": "POST",
            "post_data": "",
            "headers": {},
        }
    ]

    docs = _api_documents_for_year(page, "TEST3", 2024, templates)

    assert len(docs) == 1

    _, kwargs = request.calls[0]

    assert kwargs["data"] is None


def test_api_documents_for_year_accepts_get_template():
    payload = {
        "data": {
            "document_metas": [
                {
                    "file_year": 2024,
                    "file_url": "https://example/get.pdf",
                }
            ]
        }
    }

    request = FakeRequest([FakeResponse(payload)])
    page = FakePage(request)

    templates = [
        {
            "url": "https://api.example/test",
            "method": "GET",
            "post_data": "",
            "headers": {},
        }
    ]

    docs = _api_documents_for_year(page, "TEST3", 2024, templates)

    assert len(docs) == 1

    _, kwargs = request.calls[0]

    assert kwargs["method"] == "GET"
