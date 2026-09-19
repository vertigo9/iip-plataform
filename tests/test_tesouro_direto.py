from datetime import date

import pytest

from iip.sources.tesouro_direto import (
    NTNB_TITLE,
    long_ntnb_rate,
    parse_rates,
)
from iip.sources.tesouro_direto_harvester import TesouroDiretoHTTPHarvester

HEADER = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha"
)


def _line(titulo, venc, base, compra, venda):
    return f"{titulo};{venc};{base};{compra};{venda};1000,00;990,00;990,00"


def _csv(*lines):
    return "\r\n".join([HEADER, *lines]) + "\r\n"


LATEST = [
    _line(NTNB_TITLE, "15/05/2045", "17/09/2026", "7,31", "7,43"),
    _line(NTNB_TITLE, "15/08/2060", "17/09/2026", "7,18", "7,30"),
    _line(NTNB_TITLE, "15/05/2035", "17/09/2026", "7,54", "7,66"),
    _line(
        "Tesouro IPCA+", "15/08/2050", "17/09/2026", "7,19", "7,31"
    ),  # principal, no coupon
    _line("Tesouro Prefixado", "01/01/2031", "17/09/2026", "14,07", "14,19"),
    _line(NTNB_TITLE, "15/08/2060", "16/09/2026", "9,00", "9,10"),  # older day
]


def test_long_ntnb_rate_takes_longest_maturity_and_the_sale_rate():
    rate = long_ntnb_rate(parse_rates(_csv(*LATEST)), today=date(2026, 9, 18))

    assert rate is not None
    assert rate.maturity == date(2060, 8, 15)
    assert rate.reference_date == date(2026, 9, 17)
    # "Taxa Venda" (what an investor locks in), as a fraction -- not "Compra" 7.18
    assert rate.real_yield == 0.073


def test_only_the_coupon_bearing_ntnb_is_considered():
    only_principal = [
        _line("Tesouro IPCA+", "15/08/2060", "17/09/2026", "7,19", "7,31")
    ]

    assert (
        long_ntnb_rate(parse_rates(_csv(*only_principal)), today=date(2026, 9, 18))
        is None
    )


def test_uses_newest_business_day_regardless_of_row_order():
    rows = list(reversed(LATEST))  # oldest first

    rate = long_ntnb_rate(parse_rates(_csv(*rows)), today=date(2026, 9, 18))

    assert rate.reference_date == date(2026, 9, 17)
    assert rate.real_yield == 0.073


def test_stale_data_is_unavailable_not_used():
    assert long_ntnb_rate(parse_rates(_csv(*LATEST)), today=date(2026, 10, 30)) is None
    assert (
        long_ntnb_rate(
            parse_rates(_csv(*LATEST)), today=date(2026, 10, 30), max_age_days=60
        )
        is not None
    )


@pytest.mark.parametrize("venda", ["0,00", "-1,20", "70,00"])
def test_implausible_real_yield_is_refused(venda):
    rows = [_line(NTNB_TITLE, "15/08/2060", "17/09/2026", "7,00", venda)]

    assert long_ntnb_rate(parse_rates(_csv(*rows)), today=date(2026, 9, 18)) is None


def test_parse_skips_malformed_rows_and_handles_thousands_separator():
    text = _csv(
        "lixo;sem;datas;x;y;1;2;3",
        _line(NTNB_TITLE, "15/08/2060", "17/09/2026", "7,18", "7,30"),
    )

    rows = parse_rates(text)

    assert len(rows) == 1
    assert rows[0].taxa_venda == 7.30


def test_drop_last_line_discards_a_truncated_partial_row():
    text = _csv(
        _line(NTNB_TITLE, "15/08/2060", "17/09/2026", "7,18", "7,30"),
        "Tesouro IPCA+ com Juros Semestrais;15/05/20",  # cut by a ranged read
    )

    assert len(parse_rates(text, drop_last_line=True)) == 1


# --- transport ---------------------------------------------------------------


class _Response:
    def __init__(self, body: str, status: int):
        self.status = status
        self._body = body.encode("latin-1")

    def read(self):
        return self._body


def test_harvester_sends_a_range_request_and_handles_partial_content():
    seen = {}

    def opener(request, timeout):
        seen["range"] = request.get_header("Range")
        # 206: body cut mid-line, must not break parsing
        return _Response(_csv(*LATEST) + "Tesouro IPCA+ com Juros Sem", 206)

    rate = TesouroDiretoHTTPHarvester(opener).fetch_long_ntnb_rate(
        today=date(2026, 9, 18)
    )

    assert seen["range"].startswith("bytes=0-")
    assert rate.real_yield == 0.073


def test_harvester_handles_a_server_that_ignores_range():
    rate = TesouroDiretoHTTPHarvester(
        lambda request, timeout: _Response(_csv(*LATEST), 200)
    ).fetch_long_ntnb_rate(today=date(2026, 9, 18))

    assert rate.maturity == date(2060, 8, 15)
