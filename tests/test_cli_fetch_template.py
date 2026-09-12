from iip.cli.fetch_template import (
    build_fii_template,
    compute_dividend_yield_ttm,
    latest_complemento_for_cnpj,
)
from iip.sources.cvm_fii import FiiComplemento

CNPJ = "11.839.593/0001-09"


def make_complemento(data_referencia, dy_mes=None, pl=None, vp_cota=None, cotas=None, cnpj=CNPJ):
    valores = {}
    if dy_mes is not None:
        valores["Percentual_Dividend_Yield_Mes"] = dy_mes
    if pl is not None:
        valores["Patrimonio_Liquido"] = pl
    if vp_cota is not None:
        valores["Valor_Patrimonial_Cotas"] = vp_cota
    if cotas is not None:
        valores["Cotas_Emitidas"] = cotas
    return FiiComplemento(
        cnpj_fundo_classe=cnpj,
        data_referencia=data_referencia,
        versao="1",
        valores=valores,
    )


# Real monthly DY values found for BTLG11 earlier this session
BTLG11_MESES_2026 = [
    make_complemento("2026-01-01", dy_mes=0.009116),
    make_complemento("2026-02-01", dy_mes=0.005334),
    make_complemento("2026-03-01", dy_mes=0.007456),
    make_complemento("2026-04-01", dy_mes=0.011364),
    make_complemento("2026-05-01", dy_mes=0.002987, pl=7105228967.29),
    make_complemento("2026-06-01", dy_mes=0.008562, pl=7427406877.13),
    make_complemento(
        "2026-07-01",
        dy_mes=0.009476,
        pl=7580921710.93,
        vp_cota=15.16,
        cotas=500000000,
    ),
]


def test_compute_dividend_yield_ttm_sums_available_months():
    dy_pct, months_used = compute_dividend_yield_ttm(BTLG11_MESES_2026)
    esperado = sum(
        [0.009116, 0.005334, 0.007456, 0.011364, 0.002987, 0.008562, 0.009476]
    ) * 100
    assert months_used == 7
    assert round(dy_pct, 4) == round(esperado, 4)


def test_compute_dividend_yield_ttm_caps_at_twelve_months():
    treze_meses = [make_complemento(f"2025-{m:02d}-01", dy_mes=0.01) for m in range(1, 13)]
    treze_meses.append(make_complemento("2026-01-01", dy_mes=0.01))
    _dy_pct, months_used = compute_dividend_yield_ttm(treze_meses)
    assert months_used == 12


def test_compute_dividend_yield_ttm_returns_none_with_no_data():
    dy_pct, months_used = compute_dividend_yield_ttm([])
    assert dy_pct is None
    assert months_used == 0


def test_compute_dividend_yield_ttm_ignores_missing_values():
    com_lacuna = [
        make_complemento("2026-01-01", dy_mes=0.01),
        make_complemento("2026-02-01"),  # sem dy_mes
    ]
    dy_pct, months_used = compute_dividend_yield_ttm(com_lacuna)
    assert months_used == 1
    assert round(dy_pct, 4) == 1.0


def test_latest_complemento_for_cnpj_picks_most_recent():
    latest = latest_complemento_for_cnpj(BTLG11_MESES_2026, CNPJ)
    assert latest.data_referencia == "2026-07-01"


def test_latest_complemento_for_cnpj_normalizes_punctuation():
    latest = latest_complemento_for_cnpj(BTLG11_MESES_2026, "11839593000109")
    assert latest is not None


def test_latest_complemento_for_cnpj_returns_none_when_no_match():
    assert latest_complemento_for_cnpj(BTLG11_MESES_2026, "00000000000000") is None


DEFAULT_FINANCIALS = {
    "dividend_yield": 0,
    "assets_under_management_millions": 100,
    "reit_premium_discount": 0.0,
    "occupancy_rate": 0.85,  # exemplo de campo que NUNCA deve ser sobrescrito
}


def test_build_fii_template_fills_dividend_yield_aum_and_premium():
    template, _resultado = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50
    )

    assert template["symbol"] == "BTLG11"
    assert template["price"] == 95.50
    assert template["financials"]["dividend_yield"] != 0  # foi preenchido
    assert template["financials"]["assets_under_management_millions"] == round(
        7580921710.93 / 1_000_000, 2
    )
    esperado_premium = (95.50 - 15.16) / 15.16
    assert template["financials"]["reit_premium_discount"] == round(esperado_premium, 4)


def test_build_fii_template_computes_market_cap_from_price_and_cotas():
    template, _ = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50
    )
    assert template["market_cap"] == round(95.50 * 500000000, 2)


def test_build_fii_template_never_overwrites_unfetchable_fields():
    template, _ = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50
    )
    # occupancy_rate não é buscável — deve continuar no default, intocado
    assert template["financials"]["occupancy_rate"] == 0.85


def test_build_fii_template_reports_which_fields_were_fetched():
    _, resultado = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50
    )
    assert "dividend_yield" in resultado.fetched_fields
    assert "assets_under_management_millions" in resultado.fetched_fields
    assert "reit_premium_discount" in resultado.fetched_fields
    assert "market_cap" in resultado.fetched_fields
    assert "occupancy_rate" not in resultado.fetched_fields


def test_build_fii_template_warns_when_ttm_is_partial():
    _, resultado = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50
    )
    assert resultado.dividend_yield_months_used == 7
    assert any("7 mes" in w for w in resultado.warnings)


def test_build_fii_template_warns_when_cnpj_not_found():
    template, resultado = build_fii_template(
        "XXXX11", "00000000000000", BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=10.0
    )
    assert any("Nenhum registro CVM encontrado" in w for w in resultado.warnings)
    # nada de FII foi preenchido, so os defaults permanecem
    assert template["financials"]["dividend_yield"] == 0
    assert template["financials"]["assets_under_management_millions"] == 100


def test_build_fii_template_handles_no_price():
    template, resultado = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=None
    )
    assert template["price"] is None
    assert template["market_cap"] is None
    assert "reit_premium_discount" not in resultado.fetched_fields
    assert any("Preço não informado" in w for w in resultado.warnings)


def make_geral(**overrides):
    from iip.sources.cvm_fii import FiiGeral

    defaults = {
        "cnpj_fundo_classe": CNPJ,
        "data_referencia": "2026-07-01",
        "versao": "1",
        "tipo_fundo_classe": "Classe",
        "nome_fundo_classe": "BTGP LOGISTICA FII",
        "segmento_atuacao": "Logistica",
        "tipo_gestao": "Ativa",
        "mandato": "Renda",
        "nome_administrador": "BTG PACTUAL",
        "cnpj_administrador": "123",
        "cidade": "SAO PAULO",
        "estado": "SP",
        "outros_campos": {},
    }
    defaults.update(overrides)
    return FiiGeral(**defaults)


def test_build_fii_template_fills_sector_from_segmento_atuacao():
    template, resultado = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50,
        geral=[make_geral()],
    )
    assert template["sector"] == "Logistica"
    assert "sector" in resultado.fetched_fields


def test_build_fii_template_sector_stays_placeholder_without_geral():
    template, _ = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50
    )
    assert template["sector"] == "REPLACE_WITH_SECTOR"


def test_build_fii_template_sector_stays_placeholder_when_cnpj_not_in_geral():
    template, _ = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50,
        geral=[make_geral(cnpj_fundo_classe="00.000.000/0001-00")],
    )
    assert template["sector"] == "REPLACE_WITH_SECTOR"


def test_build_fii_template_sector_picks_most_recent_geral_row():
    template, _ = build_fii_template(
        "BTLG11", CNPJ, BTLG11_MESES_2026, DEFAULT_FINANCIALS, price=95.50,
        geral=[
            make_geral(data_referencia="2026-01-01", segmento_atuacao="Antigo"),
            make_geral(data_referencia="2026-07-01", segmento_atuacao="Logistica"),
        ],
    )
    assert template["sector"] == "Logistica"
