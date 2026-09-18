import io
import zipfile

import pytest

from iip.sources.cvm_dfp import (
    build_target,
    extract_fundamentals,
    parse_bpa_con,
    parse_bpa_ind,
    parse_bpp_con,
    parse_bpp_ind,
    parse_dre_con,
    parse_dre_ind,
)

HEADER = "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"
DRE_HEADER = "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA"

NON_FINANCIAL_CNPJ = "89.637.490/0001-45"
BANK_CNPJ = "28.195.667/0001-06"
HOLDING_CNPJ = "17.344.597/0001-94"


def _row(cnpj, ordem, cd_conta, ds_conta, valor, *, dre=False):
    if dre:
        return (
            f"{cnpj};2025-12-31;1;X;1;Y;REAL;MIL;{ordem};2025-01-01;2025-12-31;"
            f"{cd_conta};{ds_conta};{valor};S"
        )
    return f"{cnpj};2025-12-31;1;X;1;Y;REAL;MIL;{ordem};2025-12-31;{cd_conta};{ds_conta};{valor};S"


def make_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        # BPA_con: non-financial company + holding (bank stays _ind only)
        bpa_con_rows = [
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "1", "Ativo Total", "63796777"),
            _row(NON_FINANCIAL_CNPJ, "PENÚLTIMO", "1", "Ativo Total", "60000000"),
            _row(HOLDING_CNPJ, "ÚLTIMO", "1", "Ativo Total", "23097696"),
        ]
        zf.writestr(
            "dfp_cia_aberta_BPA_con_2025.csv",
            "\r\n".join([HEADER, *bpa_con_rows]).encode("latin-1"),
        )

        # BPA_ind: bank only (no _con for it)
        bpa_ind_rows = [
            _row(BANK_CNPJ, "ÚLTIMO", "1", "Ativo Total", "63848627"),
        ]
        zf.writestr(
            "dfp_cia_aberta_BPA_ind_2025.csv",
            "\r\n".join([HEADER, *bpa_ind_rows]).encode("latin-1"),
        )

        # BPP_con: non-financial (with Passivo Não Circulante) + holding
        bpp_con_rows = [
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "2", "Passivo Total", "63796777"),
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "2.01", "Passivo Circulante", "8767398"),
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "2.02", "Passivo Não Circulante", "40628278"),
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "2.03", "Patrimônio Líquido Consolidado", "14401101"),
            _row(NON_FINANCIAL_CNPJ, "PENÚLTIMO", "2.03", "Patrimônio Líquido Consolidado", "13000000"),
            _row(HOLDING_CNPJ, "ÚLTIMO", "2", "Passivo Total", "23097696"),
            _row(HOLDING_CNPJ, "ÚLTIMO", "2.03", "Patrimônio Líquido Consolidado", "10384393"),
        ]
        zf.writestr(
            "dfp_cia_aberta_BPP_con_2025.csv",
            "\r\n".join([HEADER, *bpp_con_rows]).encode("latin-1"),
        )

        # BPP_ind: bank only, no circulante/não-circulante split, equity at 2.07
        bpp_ind_rows = [
            _row(BANK_CNPJ, "ÚLTIMO", "2", "Passivo Total", "63848627"),
            _row(BANK_CNPJ, "ÚLTIMO", "2.07", "Patrimônio Líquido", "6758948"),
        ]
        zf.writestr(
            "dfp_cia_aberta_BPP_ind_2025.csv",
            "\r\n".join([HEADER, *bpp_ind_rows]).encode("latin-1"),
        )

        # DRE_con: non-financial with real EBIT line + holding with zeroed revenue
        dre_con_rows = [
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "3.01", "Receita de Venda de Bens e/ou Serviços", "20697507", dre=True),
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "3.05", "Resultado Antes do Resultado Financeiro e dos Tributos", "4480349", dre=True),
            _row(NON_FINANCIAL_CNPJ, "ÚLTIMO", "3.11", "Lucro/Prejuízo Consolidado do Período", "1678211", dre=True),
            _row(NON_FINANCIAL_CNPJ, "PENÚLTIMO", "3.01", "Receita de Venda de Bens e/ou Serviços", "18000000", dre=True),
            _row(NON_FINANCIAL_CNPJ, "PENÚLTIMO", "3.11", "Lucro/Prejuízo Consolidado do Período", "1500000", dre=True),
            _row(HOLDING_CNPJ, "ÚLTIMO", "3.01", "Receitas das Atividades Seguradoras/Resseguradoras", "0", dre=True),
            _row(HOLDING_CNPJ, "ÚLTIMO", "3.11", "Lucro/Prejuízo Consolidado do Período", "9017329", dre=True),
        ]
        zf.writestr(
            "dfp_cia_aberta_DRE_con_2025.csv",
            "\r\n".join([DRE_HEADER, *dre_con_rows]).encode("latin-1"),
        )

        # DRE_ind: bank only, no EBIT-equivalent line at all
        dre_ind_rows = [
            _row(BANK_CNPJ, "ÚLTIMO", "3.01", "Receitas de Intermediação Financeira", "8473673", dre=True),
            _row(BANK_CNPJ, "ÚLTIMO", "3.05", "Resultado antes dos Tributos sobre o Lucro", "1198995", dre=True),
            _row(BANK_CNPJ, "ÚLTIMO", "3.11", "Lucro ou Prejuízo Líquido do Período", "1002000", dre=True),
            _row(BANK_CNPJ, "ÚLTIMO", "3.99", "Lucro por Ação (R$/Ação)", "0", dre=True),
        ]
        zf.writestr(
            "dfp_cia_aberta_DRE_ind_2025.csv",
            "\r\n".join([DRE_HEADER, *dre_ind_rows]).encode("latin-1"),
        )
    return buffer.getvalue()


@pytest.fixture
def parsed():
    body = make_zip()
    return {
        "bpa_con": parse_bpa_con(body),
        "bpa_ind": parse_bpa_ind(body),
        "bpp_con": parse_bpp_con(body),
        "bpp_ind": parse_bpp_ind(body),
        "dre_con": parse_dre_con(body),
        "dre_ind": parse_dre_ind(body),
    }


def test_build_target_rejects_years_before_cvm_coverage():
    with pytest.raises(ValueError, match="2010"):
        build_target(2005)


def test_build_target_url_shape():
    target = build_target(2025)
    assert target.url == "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip"
    assert target.ticker == "MULTI"


def test_non_financial_company_uses_consolidated_and_finds_real_ebit(parsed):
    result = extract_fundamentals(2025, NON_FINANCIAL_CNPJ, **parsed)
    assert result is not None
    assert result.consolidado is True
    assert result.ativo_total == 63796777.0
    assert result.patrimonio_liquido == 14401101.0
    assert result.receita == 20697507.0
    assert result.lucro_liquido == 1678211.0
    assert result.ebit == 4480349.0
    assert result.passivo_nao_circulante == 40628278.0


def test_bank_falls_back_to_individual_and_has_no_ebit(parsed):
    result = extract_fundamentals(2025, BANK_CNPJ, **parsed)
    assert result is not None
    assert result.consolidado is False
    assert result.ativo_total == 63848627.0
    # equity line is at a different CD_CONTA (2.07, not 2.03) for a bank --
    # matched by description text, not position.
    assert result.patrimonio_liquido == 6758948.0
    assert result.lucro_liquido == 1002000.0
    assert result.ebit is None
    assert result.passivo_nao_circulante is None


def test_holding_company_zeroed_revenue_is_treated_as_unavailable(parsed):
    result = extract_fundamentals(2025, HOLDING_CNPJ, **parsed)
    assert result is not None
    assert result.receita is None  # genuinely 0 in the source -- not reported as a real 0
    assert result.lucro_liquido == 9017329.0


def test_unknown_cnpj_returns_none(parsed):
    result = extract_fundamentals(2025, "00.000.000/0000-00", **parsed)
    assert result is None
