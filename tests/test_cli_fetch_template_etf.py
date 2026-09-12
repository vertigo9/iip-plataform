from iip.cli.fetch_template import build_etf_template, latest_informe_for_cnpj
from iip.sources.cvm_renda_fixa import InformeDiario

CNPJ = "04.828.276/0001-00"  # BOVA11 (exemplo)


def make_informe(data_competencia, patrimonio=None, valor_total=None, valor_cota=None, cnpj=CNPJ):
    return InformeDiario(
        tipo_fundo_classe="FUNDO DE INDICE",
        cnpj_fundo_classe=cnpj,
        id_subclasse=None,
        data_competencia=data_competencia,
        valor_total=valor_total,
        valor_cota=valor_cota,
        patrimonio_liquido=patrimonio,
        captacao_dia=0.0,
        resgate_dia=0.0,
        numero_cotistas=100,
    )


INFORMES_AGOSTO = [
    make_informe("2026-08-03", patrimonio=15_000_000_000, valor_total=15_050_000_000, valor_cota=110.5),
    make_informe("2026-08-04", patrimonio=15_020_000_000, valor_total=15_070_000_000, valor_cota=110.7),
    make_informe("2026-08-05", patrimonio=15_100_000_000, valor_total=15_150_000_000, valor_cota=111.0),
]

DEFAULT_FINANCIALS = {
    "assets_under_management_millions": 100,
    "expense_ratio_pct": 0.5,
    "tracking_error_pct": 0.5,
}


def test_latest_informe_for_cnpj_picks_most_recent():
    latest = latest_informe_for_cnpj(INFORMES_AGOSTO, CNPJ)
    assert latest.data_competencia == "2026-08-05"


def test_latest_informe_for_cnpj_normalizes_punctuation():
    latest = latest_informe_for_cnpj(INFORMES_AGOSTO, "04828276000100")
    assert latest is not None


def test_latest_informe_for_cnpj_returns_none_when_no_match():
    assert latest_informe_for_cnpj(INFORMES_AGOSTO, "00000000000000") is None


def test_build_etf_template_fills_aum_from_latest_informe():
    template, resultado = build_etf_template(
        "BOVA11", CNPJ, INFORMES_AGOSTO, DEFAULT_FINANCIALS, price=112.30
    )
    assert template["financials"]["assets_under_management_millions"] == round(
        15_100_000_000 / 1_000_000, 2
    )
    assert "assets_under_management_millions" in resultado.fetched_fields


def test_build_etf_template_computes_market_cap_from_implied_cotas():
    template, _ = build_etf_template(
        "BOVA11", CNPJ, INFORMES_AGOSTO, DEFAULT_FINANCIALS, price=112.30
    )
    cotas_implicitas = 15_150_000_000 / 111.0
    esperado = round(112.30 * cotas_implicitas, 2)
    assert template["market_cap"] == esperado


def test_build_etf_template_never_overwrites_unfetchable_fields():
    template, _ = build_etf_template(
        "BOVA11", CNPJ, INFORMES_AGOSTO, DEFAULT_FINANCIALS, price=112.30
    )
    # expense_ratio_pct e tracking_error_pct nao sao buscaveis do Informe Diario
    assert template["financials"]["expense_ratio_pct"] == 0.5
    assert template["financials"]["tracking_error_pct"] == 0.5


def test_build_etf_template_does_not_fill_ytd_style_fields():
    _template, resultado = build_etf_template(
        "BOVA11", CNPJ, INFORMES_AGOSTO, DEFAULT_FINANCIALS, price=112.30
    )
    # net_inflows_ytd nao esta no default_financials de teste, mas o
    # importante e que nunca aparece em fetched_fields, mesmo se estivesse
    assert "net_inflows_ytd_millions" not in resultado.fetched_fields
    assert "aum_growth_3y_pct" not in resultado.fetched_fields


def test_build_etf_template_warns_about_partial_month_limits():
    _, resultado = build_etf_template(
        "BOVA11", CNPJ, INFORMES_AGOSTO, DEFAULT_FINANCIALS, price=112.30
    )
    assert any("único mês" in w for w in resultado.warnings)


def test_build_etf_template_warns_when_cnpj_not_found():
    template, resultado = build_etf_template(
        "XYZ11", "00000000000000", INFORMES_AGOSTO, DEFAULT_FINANCIALS, price=10.0
    )
    assert any("Nenhum registro CVM" in w for w in resultado.warnings)
    assert template["financials"]["assets_under_management_millions"] == 100


def test_build_etf_template_handles_no_price():
    template, resultado = build_etf_template(
        "BOVA11", CNPJ, INFORMES_AGOSTO, DEFAULT_FINANCIALS, price=None
    )
    assert template["price"] is None
    assert template["market_cap"] is None
    assert any("Preço não informado" in w for w in resultado.warnings)
