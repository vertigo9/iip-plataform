import io
import zipfile

import pytest

from iip.sources.cvm_fii import (
    build_target,
    parse_ativo_passivo,
    parse_complemento,
    parse_geral,
)

GERAL_HEADER = (
    "Tipo_Fundo_Classe;CNPJ_Fundo_Classe;Data_Referencia;Versao;Data_Entrega;"
    "Nome_Fundo_Classe;Data_Funcionamento;Publico_Alvo;Codigo_ISIN;"
    "Quantidade_Cotas_Emitidas;Fundo_Exclusivo;Cotistas_Vinculo_Familiar;Mandato;"
    "Segmento_Atuacao;Tipo_Gestao;Prazo_Duracao;Data_Prazo_Duracao;"
    "Encerramento_Exercicio_Social;Mercado_Negociacao_Bolsa;Mercado_Negociacao_MBO;"
    "Mercado_Negociacao_MB;Entidade_Administradora_BVMF;Entidade_Administradora_CETIP;"
    "Nome_Administrador;CNPJ_Administrador;Logradouro;Numero;Complemento;Bairro;"
    "Cidade;Estado;CEP;Telefone1;Telefone2;Telefone3;Site;Email"
)
GERAL_ROW = (
    "Classe;11.839.593/0001-09;2026-07-01;1;2026-08-15;BTGP LOGISTICA FII;"
    "2010-08-16;INVESTIDORES EM GERAL;BRBTLGCTF006;500000000;N;N;;Logistica;"
    "Definida;Indeterminado;;31/12;S;N;N;S;N;BTG PACTUAL SERVICOS FINANCEIROS;"
    "59281253000123;AV BRIGADEIRO FARIA LIMA;3477;;ITAIM BIBI;SAO PAULO;SP;"
    "04538133;1123958400;;;www.btgpactual.com;ri@btgpactual.com"
)

AP_HEADER = (
    "CNPJ_Fundo_Classe;Data_Referencia;Versao;Total_Necessidades_Liquidez;"
    "Disponibilidades;Titulos_Publicos;Direitos_Bens_Imoveis;Total_Passivo"
)
AP_ROW = "11.839.593/0001-09;2026-07-01;1;100000000;500000;;7000000000;50000000"
AP_ROW_MISSING = "11.839.593/0001-09;2026-06-01;1;;;;;"

COMP_HEADER = (
    "CNPJ_Fundo_Classe;Data_Referencia;Versao;Total_Numero_Cotistas;"
    "Valor_Ativo;Patrimonio_Liquido;Cotas_Emitidas;Valor_Patrimonial_Cotas;"
    "Percentual_Dividend_Yield_Mes"
)
COMP_ROW = (
    "11.839.593/0001-09;2026-07-01;1;451520;7600000000;7580921710.93;"
    "500000000;15.16;0.009476"
)


def make_zip(geral_rows=(GERAL_ROW,), ap_rows=(AP_ROW,), comp_rows=(COMP_ROW,)) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        geral_content = "\r\n".join([GERAL_HEADER, *geral_rows]).encode("latin-1")
        zf.writestr("inf_mensal_fii_geral_2026.csv", geral_content)

        ap_content = "\r\n".join([AP_HEADER, *ap_rows]).encode("latin-1")
        zf.writestr("inf_mensal_fii_ativo_passivo_2026.csv", ap_content)

        comp_content = "\r\n".join([COMP_HEADER, *comp_rows]).encode("latin-1")
        zf.writestr("inf_mensal_fii_complemento_2026.csv", comp_content)
    return buffer.getvalue()


def test_build_target_formats_url():
    target = build_target(2026)
    assert target.url == (
        "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_2026.zip"
    )
    assert target.ano == 2026


def test_build_target_rejects_years_before_2016():
    with pytest.raises(ValueError):
        build_target(2010)


def test_build_target_accepts_first_available_year():
    target = build_target(2016)
    assert target.ano == 2016


def test_parse_geral_extracts_identity_fields():
    resultado = parse_geral(make_zip())
    assert len(resultado) == 1
    fundo = resultado[0]
    assert fundo.cnpj_fundo_classe == "11.839.593/0001-09"
    assert fundo.nome_fundo_classe == "BTGP LOGISTICA FII"
    assert fundo.segmento_atuacao == "Logistica"
    assert fundo.nome_administrador == "BTG PACTUAL SERVICOS FINANCEIROS"
    assert fundo.cidade == "SAO PAULO"
    assert fundo.estado == "SP"


def test_parse_geral_keeps_remaining_columns_in_outros_campos():
    fundo = parse_geral(make_zip())[0]
    assert fundo.outros_campos["Codigo_ISIN"] == "BRBTLGCTF006"
    assert fundo.outros_campos["Email"] == "ri@btgpactual.com"


def test_parse_geral_treats_empty_mandato_as_none():
    fundo = parse_geral(make_zip())[0]
    assert fundo.mandato is None


def test_parse_ativo_passivo_extracts_identity_and_values():
    resultado = parse_ativo_passivo(make_zip())
    assert len(resultado) == 1
    linha = resultado[0]
    assert linha.cnpj_fundo_classe == "11.839.593/0001-09"
    assert linha.data_referencia == "2026-07-01"
    assert linha.valores["Total_Necessidades_Liquidez"] == 100000000.0
    assert linha.valores["Direitos_Bens_Imoveis"] == 7000000000.0


def test_parse_ativo_passivo_treats_empty_cells_as_none_not_zero():
    resultado = parse_ativo_passivo(make_zip(ap_rows=(AP_ROW, AP_ROW_MISSING)))
    linha_vazia = next(r for r in resultado if r.data_referencia == "2026-06-01")
    assert linha_vazia.valores["Total_Necessidades_Liquidez"] is None
    assert linha_vazia.valores["Disponibilidades"] is None


def test_parse_complemento_extracts_dividend_yield_and_nav():
    resultado = parse_complemento(make_zip())
    assert len(resultado) == 1
    linha = resultado[0]
    assert linha.valores["Patrimonio_Liquido"] == 7580921710.93
    assert linha.valores["Percentual_Dividend_Yield_Mes"] == 0.009476


def test_parse_functions_handle_multiple_rows():
    zip_bytes = make_zip(
        comp_rows=(
            COMP_ROW,
            "11.839.593/0001-09;2026-06-01;1;450000;7500000000;7462668094.76;"
            "500000000;14.93;0.011364",
        )
    )
    resultado = parse_complemento(zip_bytes)
    assert len(resultado) == 2
    datas = {r.data_referencia for r in resultado}
    assert datas == {"2026-07-01", "2026-06-01"}


def test_parse_ativo_passivo_treats_garbage_value_as_none():
    linha_garbage = "11.839.593/0001-09;2026-05-01;1;n/d;;;;"
    resultado = parse_ativo_passivo(make_zip(ap_rows=(linha_garbage,)))
    assert resultado[0].valores["Total_Necessidades_Liquidez"] is None


def test_parse_geral_returns_empty_tuple_when_file_missing_from_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("inf_mensal_fii_ativo_passivo_2026.csv", AP_HEADER + "\r\n" + AP_ROW)
    assert parse_geral(buffer.getvalue()) == ()
