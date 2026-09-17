from datetime import date

from iip.data.b3_notas import (
    aggregate_positions,
    parse_nota_corretagem_text,
)


def test_parses_a_single_vista_trade_line():
    text = "BOVESPA C VISTA ALZR11 CI @ 6 R$ 9,97 R$ 59,82 D"

    trades = parse_nota_corretagem_text(
        text, trade_date=date(2026, 8, 4), note_number="9395"
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade.ticker == "ALZR11"
    assert trade.buy_sell == "C"
    assert trade.market_type == "VISTA"
    assert trade.quantity == 6
    assert trade.price == 9.97
    assert trade.value == 59.82


def test_strips_f_suffix_only_for_fracionario_market():
    text = "BOVESPA C FRACIONARIO CSUD3F ON NM @ 25 R$ 13,72 R$ 343,00 D"

    trades = parse_nota_corretagem_text(
        text, trade_date=date(2026, 8, 13), note_number="11131"
    )

    assert trades[0].ticker == "CSUD3"  # nao "CSUD3F"


def test_does_not_strip_suffix_for_vista_market():
    text = "BOVESPA C VISTA HGRU11 CI @ 2 R$ 116,00 R$ 232,00 D"

    trades = parse_nota_corretagem_text(
        text, trade_date=date(2026, 8, 13), note_number="11131"
    )

    assert trades[0].ticker == "HGRU11"


def test_parses_a_sell_trade_with_credit():
    text = "BOVESPA V VISTA PVBI11 CI @ 37 R$ 65,89 R$ 2.437,93 C"

    trades = parse_nota_corretagem_text(
        text, trade_date=date(2026, 8, 14), note_number="17600"
    )

    assert trades[0].buy_sell == "V"
    assert trades[0].value == 2437.93


def test_parses_multiple_lines_from_one_note():
    text = """BOVESPA C VISTA CDII11 CI @ 2 R$ 96,82 R$ 193,64 D
BOVESPA C VISTA JURO11 CI @ 2 R$ 94,70 R$ 189,40 D"""

    trades = parse_nota_corretagem_text(
        text, trade_date=date(2026, 8, 13), note_number="11132"
    )

    assert len(trades) == 2
    assert {t.ticker for t in trades} == {"CDII11", "JURO11"}


def test_ignores_non_trade_lines():
    text = """Nome do Cliente
Fulano de Tal
BOVESPA C VISTA ALZR11 CI @ 6 R$ 9,97 R$ 59,82 D
Total Clearing (CBLC) -R$ 59,83"""

    trades = parse_nota_corretagem_text(
        text, trade_date=date(2026, 8, 4), note_number="9395"
    )

    assert len(trades) == 1
    assert trades[0].ticker == "ALZR11"


def test_aggregates_multiple_buys_into_weighted_average_price():
    """ALZR11: 4 compras reais em datas diferentes -- confere o preco
    medio ponderado exato."""
    trades = [
        *parse_nota_corretagem_text(
            "BOVESPA C VISTA ALZR11 CI @ 6 R$ 9,97 R$ 59,82 D",
            trade_date=date(2026, 8, 4),
            note_number="9395",
        ),
        *parse_nota_corretagem_text(
            "BOVESPA C VISTA ALZR11 CI @ 6 R$ 9,92 R$ 59,52 D",
            trade_date=date(2026, 8, 7),
            note_number="12883",
        ),
        *parse_nota_corretagem_text(
            "BOVESPA C VISTA ALZR11 CI @ 25 R$ 9,78 R$ 244,50 D",
            trade_date=date(2026, 8, 13),
            note_number="11131",
        ),
        *parse_nota_corretagem_text(
            "BOVESPA C VISTA ALZR11 CI @ 7 R$ 9,83 R$ 68,81 D",
            trade_date=date(2026, 8, 14),
            note_number="17600",
        ),
    ]

    result = aggregate_positions(trades)

    assert len(result.positions) == 1
    position = result.positions[0]
    assert position.ticker == "ALZR11"
    assert position.quantity == 44
    assert round(position.average_price, 4) == 9.8330
    assert not result.warnings


def test_sell_reduces_quantity_without_changing_average_price():
    trades = [
        *parse_nota_corretagem_text(
            "BOVESPA C VISTA HGRU11 CI @ 10 R$ 100,00 R$ 1000,00 D",
            trade_date=date(2026, 8, 1),
            note_number="1",
        ),
        *parse_nota_corretagem_text(
            "BOVESPA V VISTA HGRU11 CI @ 4 R$ 110,00 R$ 440,00 C",
            trade_date=date(2026, 8, 2),
            note_number="2",
        ),
    ]

    result = aggregate_positions(trades)

    position = result.positions[0]
    assert position.quantity == 6
    assert position.average_price == 100.00  # preco medio nao muda na venda
    assert not result.warnings


def test_sell_exceeding_known_quantity_produces_honest_warning():
    """PVBI11: venda real sem compra registrada na amostra -- confirma
    que o sistema avisa em vez de esconder o historico incompleto."""
    trades = parse_nota_corretagem_text(
        "BOVESPA V VISTA PVBI11 CI @ 37 R$ 65,89 R$ 2.437,93 C",
        trade_date=date(2026, 8, 14),
        note_number="17600",
    )

    result = aggregate_positions(trades)

    assert len(result.warnings) == 1
    assert "PVBI11" in result.warnings[0]
    assert "incompleto" in result.warnings[0]
    # A posicao com quantidade negativa ainda aparece -- nao e' escondida,
    # so' vem acompanhada do aviso.
    assert result.positions[0].quantity == -37


def test_position_with_zero_net_quantity_is_not_returned():
    trades = [
        *parse_nota_corretagem_text(
            "BOVESPA C VISTA HGRU11 CI @ 10 R$ 100,00 R$ 1000,00 D",
            trade_date=date(2026, 8, 1),
            note_number="1",
        ),
        *parse_nota_corretagem_text(
            "BOVESPA V VISTA HGRU11 CI @ 10 R$ 110,00 R$ 1100,00 C",
            trade_date=date(2026, 8, 2),
            note_number="2",
        ),
    ]

    result = aggregate_positions(trades)

    assert result.positions == ()


def test_full_real_sample_matches_manually_verified_totals():
    """Reproducao completa do teste ponta-a-ponta com as 8 notas reais
    (sem dado pessoal) -- confirma os totais ja verificados a mao."""
    notas = [
        ("BOVESPA C VISTA ALZR11 CI @ 6 R$ 9,97 R$ 59,82 D", date(2026, 8, 4), "9395"),
        (
            "BOVESPA C VISTA CDII11 CI ER @ 5 R$ 98,24 R$ 491,20 D",
            date(2026, 8, 5),
            "9579",
        ),
        (
            "BOVESPA C VISTA CDII11 CI ER @ 1 R$ 97,87 R$ 97,87 D",
            date(2026, 8, 7),
            "12884",
        ),
        (
            "BOVESPA C VISTA ALZR11 CI @ 6 R$ 9,92 R$ 59,52 D",
            date(2026, 8, 7),
            "12883",
        ),
        (
            "BOVESPA C VISTA CDII11 CI @ 2 R$ 96,82 R$ 193,64 D\n"
            "BOVESPA C VISTA JURO11 CI @ 2 R$ 94,70 R$ 189,40 D",
            date(2026, 8, 13),
            "11132",
        ),
        (
            "BOVESPA C FRACIONARIO CSUD3F ON NM @ 25 R$ 13,72 R$ 343,00 D\n"
            "BOVESPA C FRACIONARIO FESA4F PN N1 @ 25 R$ 4,94 R$ 123,50 D\n"
            "BOVESPA C VISTA ALZR11 CI @ 25 R$ 9,78 R$ 244,50 D\n"
            "BOVESPA C VISTA BTCI11 CI ER @ 25 R$ 8,90 R$ 222,50 D\n"
            "BOVESPA C VISTA HGRU11 CI @ 2 R$ 116,00 R$ 232,00 D\n"
            "BOVESPA C VISTA RBVA11 CI @ 25 R$ 8,80 R$ 220,00 D",
            date(2026, 8, 13),
            "11131",
        ),
        (
            "BOVESPA C VISTA ALZR11 CI @ 7 R$ 9,83 R$ 68,81 D\n"
            "BOVESPA C VISTA BTLG11 CI @ 2 R$ 99,62 R$ 199,24 D\n"
            "BOVESPA C VISTA HGCR11 CI @ 5 R$ 89,46 R$ 447,30 D\n"
            "BOVESPA C VISTA HGRU11 CI @ 2 R$ 115,67 R$ 231,34 D\n"
            "BOVESPA V VISTA PVBI11 CI @ 37 R$ 65,89 R$ 2.437,93 C",
            date(2026, 8, 14),
            "17600",
        ),
        (
            "BOVESPA C VISTA CDII11 CI @ 2 R$ 96,86 R$ 193,72 D",
            date(2026, 8, 14),
            "17601",
        ),
    ]

    all_trades = []
    for text, trade_date, note_number in notas:
        all_trades.extend(
            parse_nota_corretagem_text(
                text, trade_date=trade_date, note_number=note_number
            )
        )

    result = aggregate_positions(all_trades)
    by_ticker = {p.ticker: p for p in result.positions}

    assert by_ticker["ALZR11"].quantity == 44
    assert by_ticker["CDII11"].quantity == 10
    assert by_ticker["JURO11"].quantity == 2
    assert by_ticker["CSUD3"].quantity == 25
    assert by_ticker["FESA4"].quantity == 25
    assert by_ticker["BTCI11"].quantity == 25
    assert by_ticker["HGRU11"].quantity == 4
    assert by_ticker["RBVA11"].quantity == 25
    assert by_ticker["BTLG11"].quantity == 2
    assert by_ticker["HGCR11"].quantity == 5
    assert by_ticker["PVBI11"].quantity == -37

    assert len(result.warnings) == 1
    assert "PVBI11" in result.warnings[0]


# ---------------------------------------------------------------------------
# Testes do formato legado "NOTA DE CORRETAGEM" (notas de 2024)
# ---------------------------------------------------------------------------

from iip.data.b3_notas import (  # noqa: E402
    LEGACY_TITLE_TO_TICKER,
    parse_legacy_nota_corretagem_text,
)


def test_legacy_parses_btlg_using_confirmed_mapping():
    text = "B3 RV LISTADO C VISTA FII BTLG CI ER 4 103,45 413,80 D"

    trades, warnings = parse_legacy_nota_corretagem_text(
        text, trade_date=date(2024, 1, 18), note_number="17490"
    )

    assert not warnings
    assert len(trades) == 1
    assert trades[0].ticker == "BTLG11"
    assert trades[0].quantity == 4
    assert trades[0].price == 103.45
    assert trades[0].value == 413.80


def test_legacy_parses_multiple_lines_with_repeated_title():
    text = """B3 RV LISTADO C VISTA FII CSHGPRIM CI 1 282,59 282,59 D
B3 RV LISTADO C VISTA FII CSHGPRIM CI 1 282,59 282,59 D
B3 RV LISTADO C VISTA FII CSHGPRIM CI 2 282,59 565,18 D
B3 RV LISTADO C VISTA FII HEDGEBS CI 5 230,00 1.150,00 D"""

    trades, warnings = parse_legacy_nota_corretagem_text(
        text, trade_date=date(2024, 1, 18), note_number="17490"
    )

    assert not warnings
    assert len(trades) == 4
    tickers = [t.ticker for t in trades]
    assert tickers == ["HGPO11", "HGPO11", "HGPO11", "HGBS11"]


def test_legacy_parses_rf_listado_with_obs_marker():
    """FIC FI BCNA CI tem '#' entre titulo e quantidade -- confirma que
    o marcador de observacao opcional nao quebra o parse."""
    text = "B3 RF LISTADO C VISTA FIC FI BCNA CI # 16 9,48 151,68 D"

    trades, warnings = parse_legacy_nota_corretagem_text(
        text, trade_date=date(2024, 1, 19), note_number="15141"
    )

    assert not warnings
    assert trades[0].ticker == "BODB11"
    assert trades[0].quantity == 16


def test_legacy_parses_cpti11_without_obs_marker():
    text = "B3 RF LISTADO C VISTA FIC IE CAP CI 5 99,60 498,00 D"

    trades, warnings = parse_legacy_nota_corretagem_text(
        text, trade_date=date(2024, 1, 18), note_number="17491"
    )

    assert not warnings
    assert trades[0].ticker == "CPTI11"
    assert trades[0].value == 498.00


def test_legacy_unknown_title_produces_warning_never_a_guessed_ticker():
    """Achado real: o formato legado nunca traz o ticker direto, so' o
    nome por extenso. Um nome fora do mapeamento confirmado pelo
    usuario NUNCA vira um ticker adivinhado -- fica de fora e gera
    aviso explicito."""
    text = "B3 RV LISTADO C VISTA FII NOVOFUNDOXYZ CI 3 50,00 150,00 D"

    trades, warnings = parse_legacy_nota_corretagem_text(
        text, trade_date=date(2024, 1, 1), note_number="X"
    )

    assert trades == []
    assert len(warnings) == 1
    assert "NOVOFUNDOXYZ" in warnings[0]
    assert "não está em LEGACY_TITLE_TO_TICKER" in warnings[0]


def test_legacy_mapping_only_contains_user_confirmed_tickers():
    """Trava de regressao: qualquer entrada nova nesse dict precisa
    vir de confirmacao explicita do usuario, nao de suposicao -- este
    teste falha se o dict crescer sem essa disciplina ser lembrada."""
    assert LEGACY_TITLE_TO_TICKER == {
        "FII BTLG CI ER": "BTLG11",
        "FII BTLG CI": "BTLG11",
        "FII CSHGPRIM CI": "HGPO11",
        "FII HEDGEBS CI": "HGBS11",
        "FIC IE CAP CI": "CPTI11",
        "FIC FI BCNA CI": "BODB11",
    }


def test_legacy_trades_aggregate_together_with_new_format_trades():
    """Confirma que TradeRecord do formato legado e' 100% compativel
    com aggregate_positions -- mesma estrutura, so' a origem do parse
    muda."""
    legacy_trades, _ = parse_legacy_nota_corretagem_text(
        "B3 RV LISTADO C VISTA FII BTLG CI ER 4 103,45 413,80 D",
        trade_date=date(2024, 1, 18),
        note_number="17490",
    )
    new_format_trades = parse_nota_corretagem_text(
        "BOVESPA C VISTA BTLG11 CI ER @ 5 R$ 100,06 R$ 500,30 D",
        trade_date=date(2026, 7, 27),
        note_number="11711",
    )

    result = aggregate_positions(legacy_trades + new_format_trades)

    assert len(result.positions) == 1
    position = result.positions[0]
    assert position.ticker == "BTLG11"
    assert position.quantity == 9  # 4 (legado) + 5 (novo)
