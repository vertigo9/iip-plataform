from iip.sources.harvester import FetchedDocument, XPAssetHTTPHarvester
from iip.sources.xp_asset import DocumentTarget


class FakeHeaders(dict):
    pass


class FakeResponse:
    status = 200

    def __init__(self, body=b"<html>XPML11</html>", url="https://final.example/xpml11"):
        self.headers = FakeHeaders({"Content-Type": "text/html; charset=utf-8"})
        self._body = body
        self._url = url

    def read(self):
        return self._body

    def geturl(self):
        return self._url


def target(year=2026):
    return DocumentTarget(
        "XPML11",
        "xp_asset",
        "institutional_primary",
        "https://www.xpasset.com.br/fundos/xp-malls/",
        year,
    )


def test_fetch_normalizes_response():
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    result = XPAssetHTTPHarvester(opener, timeout=7.5).fetch(target())
    assert isinstance(result, FetchedDocument)
    assert result.status_code == 200
    assert result.content_type == "text/html"
    assert result.body == b"<html>XPML11</html>"
    assert result.final_url == "https://final.example/xpml11"
    assert calls[0][1] == 7.5


def test_fetch_sends_headers():
    captured = {}

    def opener(request, timeout):
        captured["ua"] = request.get_header("User-agent")
        captured["accept"] = request.get_header("Accept")
        return FakeResponse()

    XPAssetHTTPHarvester(opener).fetch(target())
    assert captured["ua"] == "IIP-D-OBSIDIAN/1.0"
    assert "application/pdf" in captured["accept"]


def test_fetch_preserves_target():
    t = target(2025)

    def opener(request, timeout):
        return FakeResponse()

    assert XPAssetHTTPHarvester(opener).fetch(t).target == t


def test_fetch_many_preserves_order():
    def opener(request, timeout):
        return FakeResponse()

    result = XPAssetHTTPHarvester(opener).fetch_many(
        (target(2024), target(2025), target(2026))
    )
    assert [x.target.year for x in result] == [2024, 2025, 2026]


def test_none_status_becomes_200():
    class ResponseWithoutStatus(FakeResponse):
        pass

    response = ResponseWithoutStatus()
    response.status = None

    def opener(request, timeout):
        return response

    assert XPAssetHTTPHarvester(opener).fetch(target()).status_code == 200


def test_content_type_is_normalized():
    def opener(request, timeout):
        return FakeResponse()

    assert XPAssetHTTPHarvester(opener).fetch(target()).content_type == "text/html"


def test_final_url_falls_back_to_target():
    class MinimalResponse:
        status = 200
        headers = FakeHeaders({"Content-Type": "application/pdf"})

        def read(self):
            return b"%PDF"

    def opener(request, timeout):
        return MinimalResponse()

    result = XPAssetHTTPHarvester(opener).fetch(target())
    assert result.final_url == target().url
    assert result.content_type == "application/pdf"


def test_fetch_uses_get():
    captured = {}

    def opener(request, timeout):
        captured["method"] = request.method
        return FakeResponse()

    XPAssetHTTPHarvester(opener).fetch(target())
    assert captured["method"] == "GET"
