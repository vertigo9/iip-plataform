import json

import pytest

from iip.sources.receita_federal import build_target, parse_cnpj_response


def test_build_target_normalizes_punctuated_cnpj():
    target = build_target("06.990.590/0001-23")

    assert target.cnpj == "06990590000123"
    assert target.url == "https://brasilapi.com.br/api/cnpj/v1/06990590000123"


def test_build_target_accepts_already_normalized_cnpj():
    target = build_target("06990590000123")
    assert target.cnpj == "06990590000123"


def test_build_target_rejects_wrong_length():
    with pytest.raises(ValueError):
        build_target("123456")


def test_build_target_rejects_empty_string():
    with pytest.raises(ValueError):
        build_target("")


def make_response(**overrides):
    # Real example (Google Brasil), confirmed from public documentation.
    result = {
        "cnpj": "06990590000123",
        "razao_social": "GOOGLE BRASIL INTERNET LTDA.",
        "nome_fantasia": "",
        "descricao_situacao_cadastral": "ATIVA",
        "natureza_juridica": "206-2 - Sociedade Empresária Limitada",
        "porte": "DEMAIS",
        "capital_social": 200000000,
        "data_inicio_atividade": "2005-11-03",
        "cnae_fiscal": 6319400,
        "cnae_fiscal_descricao": "Portais, provedores de conteúdo e outros serviços",
        "cnaes_secundarios": [
            {
                "codigo": 4751201,
                "descricao": "Comércio varejista especializado de equipamentos e suprimentos de informática",
            },
            {
                "codigo": 6201501,
                "descricao": "Desenvolvimento de programas de computador sob encomenda",
            },
        ],
        "logradouro": "BRIG FARIA LIMA",
        "numero": "3477",
        "bairro": "ITAIM BIBI",
        "municipio": "SAO PAULO",
        "uf": "SP",
        "cep": "04538133",
        "email": None,
        "ddd_telefone_1": "1123958400",
        "opcao_pelo_mei": None,
    }
    result.update(overrides)
    return json.dumps(result).encode("utf-8")


def test_parse_cnpj_response_extracts_expected_fields():
    record = parse_cnpj_response(make_response())

    assert record.cnpj == "06990590000123"
    assert record.razao_social == "GOOGLE BRASIL INTERNET LTDA."
    assert record.nome_fantasia is None  # empty string normalized to None
    assert record.situacao_cadastral == "ATIVA"
    assert record.municipio == "SAO PAULO"
    assert record.uf == "SP"
    assert record.capital_social == 200000000.0


def test_parse_cnpj_response_extracts_secondary_cnaes():
    record = parse_cnpj_response(make_response())

    assert len(record.cnaes_secundarios) == 2
    assert record.cnaes_secundarios[0].codigo == 4751201
    assert "informática" in record.cnaes_secundarios[0].descricao


def test_parse_cnpj_response_handles_no_secondary_cnaes():
    record = parse_cnpj_response(make_response(cnaes_secundarios=[]))
    assert record.cnaes_secundarios == ()


def test_parse_cnpj_response_handles_missing_secondary_cnaes_key():
    body = make_response()
    data = json.loads(body)
    del data["cnaes_secundarios"]
    record = parse_cnpj_response(json.dumps(data).encode("utf-8"))
    assert record.cnaes_secundarios == ()


def test_parse_cnpj_response_handles_garbage_capital_social():
    record = parse_cnpj_response(make_response(capital_social="n/a"))
    assert record.capital_social is None
