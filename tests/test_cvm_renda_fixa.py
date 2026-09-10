import io
import zipfile

import pytest

from iip.sources.cvm_renda_fixa import (
    build_diario_target,
    build_perfil_target,
    parse_diario_response,
    parse_perfil_response,
)

DIARIO_HEADER = (
    "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;VL_TOTAL;VL_QUOTA;"
    "VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST"
)
DIARIO_ROW = (
    "CLASSES - FIF;00.017.024/0001-53;;2026-08-03;1095646.22;44.275588000000;"
    "1207786.03;0.00;0.00;1"
)
DIARIO_ROW_MISSING_QUOTA = (
    "CLASSES - FIF;00.017.024/0001-53;;2026-08-04;;;;0.00;0.00;1"
)


def make_diario_zip(rows=(DIARIO_ROW,)) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        content = "\r\n".join([DIARIO_HEADER, *rows]).encode("latin-1")
        zf.writestr("inf_diario_fi_202608.csv", content)
    return buffer.getvalue()


PERFIL_HEADER = (
    "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;DENOM_SOCIAL;DT_COMPTC;VERSAO;"
    "NR_COTST_PF_PB;VOTO_ADMIN_ASSEMB;ST_LIQDEZ"
)
PERFIL_ROW = (
    "CLASSES - FIF;00.071.477/0001-68;BB RENDA FIXA AUTOMATICO FIC;2026-08-31;4;"
    "11;nao houve assembleia;"
)


def make_perfil_csv(rows=(PERFIL_ROW,)) -> bytes:
    return "\r\n".join([PERFIL_HEADER, *rows]).encode("latin-1")


def test_build_diario_target_formats_url():
    target = build_diario_target(2026, 8)
    assert target.url == (
        "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_202608.zip"
    )


def test_build_perfil_target_formats_url_no_zip_extension():
    target = build_perfil_target(2026, 8)
    assert target.url == (
        "https://dados.cvm.gov.br/dados/FI/DOC/PERFIL_MENSAL/DADOS/"
        "perfil_mensal_fi_202608.csv"
    )
    assert target.url.endswith(".csv")


def test_build_target_zero_pads_month():
    target = build_diario_target(2026, 3)
    assert "inf_diario_fi_202603.zip" in target.url


def test_build_target_rejects_invalid_month():
    with pytest.raises(ValueError):
        build_diario_target(2026, 13)


def test_build_target_rejects_years_before_2019():
    with pytest.raises(ValueError):
        build_perfil_target(2018, 1)


def test_parse_diario_response_extracts_all_fields():
    resultado = parse_diario_response(make_diario_zip())
    assert len(resultado) == 1
    linha = resultado[0]
    assert linha.cnpj_fundo_classe == "00.017.024/0001-53"
    assert linha.data_competencia == "2026-08-03"
    assert linha.valor_cota == 44.275588
    assert linha.patrimonio_liquido == 1207786.03
    assert linha.numero_cotistas == 1


def test_parse_diario_response_treats_empty_cells_as_none():
    resultado = parse_diario_response(make_diario_zip(rows=(DIARIO_ROW_MISSING_QUOTA,)))
    linha = resultado[0]
    assert linha.valor_cota is None
    assert linha.valor_total is None
    assert linha.patrimonio_liquido is None


def test_parse_diario_response_treats_empty_cotistas_as_none():
    linha_sem_cotistas = "CLASSES - FIF;00.017.024/0001-53;;2026-08-06;1.0;1.0;1.0;0.00;0.00;"
    resultado = parse_diario_response(make_diario_zip(rows=(linha_sem_cotistas,)))
    assert resultado[0].numero_cotistas is None


def test_parse_diario_response_handles_multiple_rows():
    outro_dia = (
        "CLASSES - FIF;00.017.024/0001-53;;2026-08-04;1096222.50;44.294551800000;"
        "1208303.34;0.00;0.00;1"
    )
    resultado = parse_diario_response(make_diario_zip(rows=(DIARIO_ROW, outro_dia)))
    assert len(resultado) == 2
    datas = {r.data_competencia for r in resultado}
    assert datas == {"2026-08-03", "2026-08-04"}


def test_parse_diario_response_treats_garbage_number_as_none():
    linha_garbage = "CLASSES - FIF;00.017.024/0001-53;;2026-08-05;n/d;x;y;0.00;0.00;abc"
    resultado = parse_diario_response(make_diario_zip(rows=(linha_garbage,)))
    linha = resultado[0]
    assert linha.valor_total is None
    assert linha.valor_cota is None
    assert linha.numero_cotistas is None


def test_parse_diario_response_returns_empty_when_no_matching_file_in_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("outro_arquivo.csv", "col1;col2\r\nval1;val2")
    assert parse_diario_response(buffer.getvalue()) == ()


def test_parse_perfil_response_extracts_identity_fields():
    resultado = parse_perfil_response(make_perfil_csv())
    assert len(resultado) == 1
    perfil = resultado[0]
    assert perfil.cnpj_fundo_classe == "00.071.477/0001-68"
    assert perfil.denominacao_social == "BB RENDA FIXA AUTOMATICO FIC"
    assert perfil.data_competencia == "2026-08-31"
    assert perfil.versao == "4"


def test_parse_perfil_response_keeps_remaining_columns_as_raw_strings():
    # Values here are heterogeneous (numbers, free text, empty) — kept
    # as raw strings rather than force-parsed as float, unlike FII's
    # ativo_passivo/complemento which are purely numeric.
    perfil = parse_perfil_response(make_perfil_csv())[0]
    assert perfil.valores["NR_COTST_PF_PB"] == "11"
    assert perfil.valores["VOTO_ADMIN_ASSEMB"] == "nao houve assembleia"
    assert perfil.valores["ST_LIQDEZ"] == ""


def test_parse_perfil_response_handles_empty_data():
    body = PERFIL_HEADER.encode("latin-1")
    assert parse_perfil_response(body) == ()
