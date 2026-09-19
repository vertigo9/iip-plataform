import json

import pytest

from iip.sources.solutions_ir import (
    SOLUTIONS_IR_COMPANIES,
    build_documents_target,
    company_for_ticker,
    parse_documents_response,
)


def test_company_for_ticker_is_case_insensitive():
    company = company_for_ticker("btci11")
    assert company is not None
    assert company.ticker == "BTCI11"
    assert company.fund_id == "296809"
    assert company.cnpj == "09552812000114"


def test_company_for_ticker_unknown_returns_none():
    assert company_for_ticker("ALZR11") is None


def test_registered_tickers_are_the_fund_and_the_company_site():
    assert set(SOLUTIONS_IR_COMPANIES) == {"BTCI11", "CSUD3"}


def test_build_documents_target_uses_fund_id_and_cnpj():
    target = build_documents_target("BTCI11")
    assert target.url == "https://api.solutions-ir.com/v2/asset/296809/documents/09552812000114"
    assert target.ticker == "BTCI11"


def test_build_documents_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="ALZR11"):
        build_documents_target("ALZR11")


def _sample_response() -> bytes:
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
                                "date": "31/08/2026",
                                "link": "https://static.btgpactual.com/media/relatorio/x_RM.pdf",
                                "nome": "x_20260831_RM.pdf",
                            }
                        ],
                    },
                    {
                        "ano": "2025",
                        "historico": [
                            {
                                "data_descricao": "31/12/2025",
                                "date": "31/12/2025",
                                "link": "https://static.btgpactual.com/media/relatorio/y_RM.pdf",
                                "nome": "y_20251231_RM.pdf",
                            }
                        ],
                    },
                ],
            },
            {
                "sigla": "ATA",
                "nome_tipo": "ATAS DE ASSEMBLEIAS",
                "ano_historico": [
                    {
                        "ano": "2026",
                        "historico": [
                            {
                                "data_descricao": "10/03/2026",
                                "link": "https://static.btgpactual.com/media/ata/z_ATA.pdf",
                                "nome": "z_ATA.pdf",
                            }
                        ],
                    }
                ],
            },
        ]
    }
    return json.dumps(payload).encode("utf-8")


def test_parse_documents_response_flattens_and_extracts_fields():
    docs = parse_documents_response(_sample_response(), "BTCI11")

    assert len(docs) == 3
    assert all(d.ticker == "BTCI11" for d in docs)
    urls = {d.url for d in docs}
    assert "https://static.btgpactual.com/media/relatorio/x_RM.pdf" in urls
    assert "https://static.btgpactual.com/media/ata/z_ATA.pdf" in urls


def test_parse_documents_response_sorts_newest_year_first():
    docs = parse_documents_response(_sample_response(), "BTCI11")
    years = [d.year for d in docs]
    assert years == sorted(years, reverse=True)


def test_parse_documents_response_skips_entries_without_link():
    payload = {
        "files": [
            {
                "sigla": "RM",
                "nome_tipo": "RELATORIO MENSAL",
                "ano_historico": [
                    {"ano": "2026", "historico": [{"data_descricao": "01/01/2026"}]}
                ],
            }
        ]
    }
    docs = parse_documents_response(json.dumps(payload).encode("utf-8"), "BTCI11")
    assert docs == ()
