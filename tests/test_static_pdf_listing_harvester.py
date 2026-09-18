from iip.sources.static_pdf_listing import StaticListingTarget
from iip.sources.static_pdf_listing_harvester import StaticPdfListingHTTPHarvester


class _FakeResponse:
    def __init__(self, body: bytes, url: str, status: int = 200):
        self._body = body
        self._url = url
        self.status = status

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_parses_documents_from_html_body():
    html = b'<a href="https://fundo.com.br/uploads/Relatorio-Setembro-2026.pdf">Baixar</a>'

    def fake_opener(request, timeout):
        return _FakeResponse(html, "https://fundo.com.br/pagina/")

    harvester = StaticPdfListingHTTPHarvester(opener=fake_opener)
    target = StaticListingTarget(ticker="TICK11", url="https://fundo.com.br/pagina/")

    result = harvester.fetch(target)

    assert result.status_code == 200
    assert result.final_url == "https://fundo.com.br/pagina/"
    assert len(result.documents) == 1
    assert result.documents[0].url == "https://fundo.com.br/uploads/Relatorio-Setembro-2026.pdf"
    assert result.documents[0].ticker == "TICK11"


def test_fetch_returns_empty_documents_when_no_pdf_links():
    def fake_opener(request, timeout):
        return _FakeResponse(b"<html>sem documentos</html>", "https://fundo.com.br/pagina/")

    harvester = StaticPdfListingHTTPHarvester(opener=fake_opener)
    target = StaticListingTarget(ticker="TICK11", url="https://fundo.com.br/pagina/")

    result = harvester.fetch(target)

    assert result.documents == ()
