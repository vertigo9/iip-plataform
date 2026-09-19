import json

from iip.sources.solutions_ir import SolutionsIrTarget
from iip.sources.solutions_ir_harvester import SolutionsIrHTTPHarvester


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_parses_documents_from_json_body():
    payload = {
        "files": [
            {
                "sigla": "RM",
                "nome_tipo": "RELATORIO MENSAL",
                "ano_historico": [
                    {
                        "ano": "2026",
                        "historico": [
                            {
                                "data_descricao": "31/08/2026",
                                "link": "https://static.btgpactual.com/x.pdf",
                                "nome": "x.pdf",
                            }
                        ],
                    }
                ],
            }
        ]
    }

    def fake_opener(request, timeout):
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    harvester = SolutionsIrHTTPHarvester(opener=fake_opener)
    target = SolutionsIrTarget(
        ticker="BTCI11",
        url="https://api.solutions-ir.com/v2/asset/296809/documents/09552812000114",
    )

    result = harvester.fetch(target)

    assert result.status_code == 200
    assert len(result.documents) == 1
    assert result.documents[0].url == "https://static.btgpactual.com/x.pdf"
    assert result.documents[0].ticker == "BTCI11"


def test_fetch_returns_empty_documents_when_no_files():
    def fake_opener(request, timeout):
        return _FakeResponse(json.dumps({"files": []}).encode("utf-8"))

    harvester = SolutionsIrHTTPHarvester(opener=fake_opener)
    target = SolutionsIrTarget(
        ticker="BTCI11",
        url="https://api.solutions-ir.com/v2/asset/296809/documents/09552812000114",
    )

    result = harvester.fetch(target)

    assert result.documents == ()
