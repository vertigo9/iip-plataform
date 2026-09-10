import io
import zipfile

import pytest

from iip.sources.cvm_fiagro import build_target, parse_informe, parse_subclasse

# Real header confirmed against inf_mensal_fiagro_202508.csv (trimmed set
# of columns for the test fixture — same identity fields + a handful of
# representative numeric ones, not all 133).
INFORME_HEADER = (
    "CNPJ_Classe;Nome_Classe;Data_Referencia;Data_Entrega;Versao;Classe_Unica;"
    "CNPJ_Administrador;Nome_Administrador;Codigo_ISIN;Mercado_Negociacao;"
    "Nome_Gestor;CNPJ_Gestor;Numero_Cotistas;Patrimonio_Liquido;"
    "Valor_Patrimonial_Cotas;Dividend_Yield_Mes;Total_Passivo"
)
INFORME_ROW = (
    "40413979000144;FIAGRO RIZA AGRO IMOBILIÁRIO;2025-08-01;2025-09-10;1;N;"
    "45246410000155;BANCO GENIAL S.A.;BRRZAGCTF006;BOLSA;"
    "RIZA GESTORA DE RECURSOS LTDA.;12209584000199;82827;658972807.75;"
    "9.69;0.01;19587713.63"
)
INFORME_ROW_MISSING_YIELD = (
    "40413979000144;FIAGRO RIZA AGRO IMOBILIÁRIO;2025-07-01;2025-08-10;1;N;"
    "45246410000155;BANCO GENIAL S.A.;BRRZAGCTF006;BOLSA;"
    "RIZA GESTORA DE RECURSOS LTDA.;12209584000199;82000;650000000.00;"
    "9.50;;19000000.00"
)

SUBCLASSE_HEADER = (
    "CNPJ_Classe;Nome_Classe;Data_Referencia;Nome_Subclasse;Numero_Cotas;"
    "Valor_Patrimonial_Cota"
)
SUBCLASSE_ROW = (
    "40413979000144;FIAGRO RIZA AGRO IMOBILIÁRIO;2025-08-01;"
    "Subclasse 1 (ou classe única);68040425;9.69"
)


def make_zip(informe_rows=(INFORME_ROW,), subclasse_rows=(SUBCLASSE_ROW,)) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        informe_content = "\r\n".join([INFORME_HEADER, *informe_rows]).encode("latin-1")
        zf.writestr("inf_mensal_fiagro_202508.csv", informe_content)

        subclasse_content = "\r\n".join([SUBCLASSE_HEADER, *subclasse_rows]).encode(
            "latin-1"
        )
        zf.writestr("inf_mensal_fiagro_subclasse_202508.csv", subclasse_content)
    return buffer.getvalue()


def test_build_target_formats_url_with_competencia():
    target = build_target(2026, 8)
    assert target.url == (
        "https://dados.cvm.gov.br/dados/FIAGRO/DOC/INF_MENSAL/DADOS/"
        "inf_mensal_fiagro_202608.zip"
    )
    assert target.ano == 2026
    assert target.mes == 8


def test_build_target_zero_pads_single_digit_month():
    target = build_target(2026, 3)
    assert "inf_mensal_fiagro_202603.zip" in target.url


def test_build_target_rejects_invalid_month():
    with pytest.raises(ValueError):
        build_target(2026, 13)
    with pytest.raises(ValueError):
        build_target(2026, 0)


def test_build_target_rejects_years_before_2022():
    with pytest.raises(ValueError):
        build_target(2021, 1)


def test_parse_informe_extracts_identity_fields():
    resultado = parse_informe(make_zip())
    assert len(resultado) == 1
    fundo = resultado[0]
    assert fundo.cnpj_classe == "40413979000144"
    assert fundo.nome_classe == "FIAGRO RIZA AGRO IMOBILIÁRIO"
    assert fundo.nome_administrador == "BANCO GENIAL S.A."
    assert fundo.nome_gestor == "RIZA GESTORA DE RECURSOS LTDA."
    assert fundo.mercado_negociacao == "BOLSA"
    assert fundo.codigo_isin == "BRRZAGCTF006"


def test_parse_informe_extracts_numeric_values_in_dict():
    fundo = parse_informe(make_zip())[0]
    assert fundo.valores["Patrimonio_Liquido"] == 658972807.75
    assert fundo.valores["Dividend_Yield_Mes"] == 0.01
    assert fundo.valores["Numero_Cotistas"] == 82827.0


def test_parse_informe_treats_empty_cell_as_none_not_zero():
    resultado = parse_informe(make_zip(informe_rows=(INFORME_ROW_MISSING_YIELD,)))
    assert resultado[0].valores["Dividend_Yield_Mes"] is None


def test_parse_informe_does_not_pick_up_the_subclasse_file():
    # Both files contain "inf_mensal_fiagro_" — must not accidentally
    # parse the subclasse file as if it were the main informe.
    resultado = parse_informe(make_zip())
    assert len(resultado) == 1
    assert "Nome_Subclasse" not in resultado[0].valores


def test_parse_subclasse_extracts_fields():
    resultado = parse_subclasse(make_zip())
    assert len(resultado) == 1
    linha = resultado[0]
    assert linha.cnpj_classe == "40413979000144"
    assert linha.nome_subclasse == "Subclasse 1 (ou classe única)"
    assert linha.numero_cotas == 68040425.0
    assert linha.valor_patrimonial_cota == 9.69


def test_parse_functions_handle_multiple_funds():
    outro_fundo = (
        "12345678000199;OUTRO FIAGRO;2025-08-01;2025-09-10;1;N;"
        "11111111000111;OUTRO ADM;BROTHRAGCTF001;BOLSA;"
        "OUTRA GESTORA LTDA.;22222222000122;5000;100000000.00;"
        "10.00;0.02;3000000.00"
    )
    resultado = parse_informe(make_zip(informe_rows=(INFORME_ROW, outro_fundo)))
    assert len(resultado) == 2
    cnpjs = {r.cnpj_classe for r in resultado}
    assert cnpjs == {"40413979000144", "12345678000199"}


def test_parse_informe_returns_empty_tuple_when_file_missing():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "inf_mensal_fiagro_subclasse_202508.csv",
            SUBCLASSE_HEADER + "\r\n" + SUBCLASSE_ROW,
        )
    assert parse_informe(buffer.getvalue()) == ()
