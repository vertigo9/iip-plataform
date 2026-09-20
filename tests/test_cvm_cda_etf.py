import io
import zipfile
from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.portfolio.etf_composition import render_composition
from iip.sources.cvm_cda import CdaError
from iip.sources.cvm_cda_etf import (
    bond_weights,
    bonds_coverage,
    parse_cda_etf_zip,
    share_maturing_after_years,
    weighted_average_maturity_years,
)
from iip.sources.cvm_cda_harvester import CvmCdaHTTPHarvester, FetchedEtfCda, fetch_etf

CNPJ = "56.176.507/0001-55"
HEADER = (
    "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;DENOM_SOCIAL;DT_COMPTC;VL_PATRIM_LIQ;TP_APLIC;"
    "QT_POS_FINAL;VL_MERC_POS_FINAL;DT_VENC"
)


def _row(cnpj, tp, qty, value, venc="", pl="1000.00", dt="2026-08-31"):
    return f"CLASSES FIIM;{cnpj};INVESTO ETF;{dt};{pl};{tp};{qty};{value};{venc}"


def _zip(rows, month="202608", name=None, header=HEADER):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            name or f"cda_fie_{month}.csv",
            "\n".join([header, *rows]).encode("latin-1"),
        )
    return buffer.getvalue()


BASIC = [
    _row(CNPJ, "Títulos Públicos", "10", "400.00", "2027-03-01"),
    _row(CNPJ, "Títulos Públicos", "5", "100.00", "2027-03-01"),
    _row(CNPJ, "Títulos Públicos", "20", "490.00", "2060-08-15"),
    _row(CNPJ, "Cotas de Fundos", "3", "6.00"),
    _row(CNPJ, "Valores a pagar", "", "4.00"),
    _row("11.111.111/0001-11", "Títulos Públicos", "9", "999.00", "2030-01-01"),
]


def test_reads_the_bonds_of_the_requested_fund_only():
    portfolio = parse_cda_etf_zip(_zip(BASIC), CNPJ, "202608")

    assert portfolio.net_assets == 1000.0
    assert portfolio.reference_date == date(2026, 8, 31)
    assert len(portfolio.bonds) == 3
    assert sum(b.market_value for b in portfolio.bonds) == 990.0


def test_cnpj_is_matched_by_digits():
    assert parse_cda_etf_zip(_zip(BASIC), "56176507000155", "202608") is not None


def test_fund_absent_gives_none():
    assert parse_cda_etf_zip(_zip(BASIC), "22.222.222/0001-22", "202608") is None


def test_missing_cda_fie_file_is_an_error():
    body = _zip(BASIC, name="cda_fi_PL_202608.csv")

    with pytest.raises(CdaError):
        parse_cda_etf_zip(body, CNPJ, "202608")


def test_corrupt_archive_is_an_error():
    with pytest.raises(CdaError):
        parse_cda_etf_zip(b"not a zip", CNPJ, "202608")


def test_old_cnpj_column_name_is_accepted():
    header = HEADER.replace("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")

    assert parse_cda_etf_zip(_zip(BASIC, header=header), CNPJ, "202608") is not None


def test_untrustworthy_bond_rows_are_dropped_not_zeroed():
    rows = [
        _row(CNPJ, "Títulos Públicos", "10", "400.00", "2027-03-01"),
        _row(CNPJ, "Títulos Públicos", "10", "", "2028-03-01"),
        _row(CNPJ, "Títulos Públicos", "10", "-5.00", "2028-09-01"),
        _row(CNPJ, "Títulos Públicos", "10", "50.00", ""),
        _row(CNPJ, "Títulos Públicos", "", "50.00", "2029-03-01"),
    ]

    portfolio = parse_cda_etf_zip(_zip(rows), CNPJ, "202608")

    assert [b.market_value for b in portfolio.bonds] == [400.0]
    assert bonds_coverage(portfolio) == 0.4


def test_invalid_net_assets_gives_none():
    rows = [_row(CNPJ, "Títulos Públicos", "1", "10.00", "2027-03-01", pl="0")]

    assert parse_cda_etf_zip(_zip(rows), CNPJ, "202608") is None


def test_weights_sum_equal_maturities_and_sort():
    portfolio = parse_cda_etf_zip(_zip(BASIC), CNPJ, "202608")

    assert bond_weights(portfolio) == (
        (date(2027, 3, 1), 0.5),
        (date(2060, 8, 15), 0.49),
    )
    assert bonds_coverage(portfolio) == pytest.approx(0.99)


def test_weighted_average_maturity_and_long_dated_share():
    portfolio = parse_cda_etf_zip(_zip(BASIC), CNPJ, "202608")

    near = (date(2027, 3, 1) - date(2026, 8, 31)).days / 365.25
    far = (date(2060, 8, 15) - date(2026, 8, 31)).days / 365.25
    expected = (500 * near + 490 * far) / 990
    assert weighted_average_maturity_years(portfolio) == pytest.approx(expected)
    assert share_maturing_after_years(portfolio, 10) == pytest.approx(0.49)
    assert share_maturing_after_years(portfolio, 40) == 0.0


def test_no_bonds_gives_no_average():
    rows = [_row(CNPJ, "Cotas de Fundos", "3", "6.00")]
    portfolio = parse_cda_etf_zip(_zip(rows), CNPJ, "202608")

    assert weighted_average_maturity_years(portfolio) is None


class _Opener:
    def __init__(self, bodies):
        self.bodies = bodies
        self.urls = []

    def __call__(self, request, timeout=0):
        from urllib.error import HTTPError

        self.urls.append(request.full_url)
        month = request.full_url.rsplit("_", 1)[1][:6]
        body = self.bodies.get(month)
        if body is None:
            raise HTTPError(request.full_url, 404, "nf", {}, None)

        class _Response:
            def read(self_inner):
                return body

        return _Response()


def test_fetch_falls_back_when_the_newest_month_is_not_published():
    opener = _Opener({"202607": _zip(BASIC, month="202607")})

    fetched = fetch_etf(CvmCdaHTTPHarvester(opener), CNPJ, months=("202608", "202607"))

    assert fetched.portfolio.month == "202607"
    assert len(opener.urls) == 2


def test_fetch_reports_what_it_tried():
    opener = _Opener({"202607": _zip(BASIC[-1:], month="202607")})

    with pytest.raises(CdaError) as excinfo:
        fetch_etf(CvmCdaHTTPHarvester(opener), CNPJ, months=("202608", "202607"))

    assert "202608 (não publicado)" in str(excinfo.value)
    assert "202607 (fundo ausente)" in str(excinfo.value)


def test_render_states_date_coverage_and_limits():
    portfolio = parse_cda_etf_zip(_zip(BASIC), CNPJ, "202608")

    text = render_composition(portfolio, "https://example/cda.zip")

    assert "31/08/2026" in text
    assert "99.0%" in text
    assert "| 01/03/2027 | 50.00% |" in text
    assert "não é duration" in text
    assert "49.0%" in text
    assert "não muda o score" in text
    assert "https://example/cda.zip" in text


def test_command_prints_and_persists_the_section(monkeypatch, tmp_path):
    portfolio = parse_cda_etf_zip(_zip(BASIC), CNPJ, "202608")
    monkeypatch.setattr(
        "iip.portfolio.etf_composition.default_fetch_etf_cda",
        lambda cnpj: FetchedEtfCda(portfolio, "https://example/cda.zip"),
    )
    vault = tmp_path / "vault"

    result = CliRunner().invoke(
        cli,
        ["etf-composition", "--ticker", "lftb11", "--persist", "--vault", str(vault)],
    )

    assert result.exit_code == 0, result.output
    assert "| 01/03/2027 | 50.00% |" in result.output
    note = next(vault.rglob("LFTB11 - Carteira e Crédito.md"))
    body = note.read_text(encoding="utf-8")
    assert "IIP:portfolio_composition" in body
    assert "31/08/2026" in body


def test_command_without_persist_writes_nothing(monkeypatch, tmp_path):
    portfolio = parse_cda_etf_zip(_zip(BASIC), CNPJ, "202608")
    monkeypatch.setattr(
        "iip.portfolio.etf_composition.default_fetch_etf_cda",
        lambda cnpj: FetchedEtfCda(portfolio, "u"),
    )

    result = CliRunner().invoke(
        cli, ["etf-composition", "--ticker", "LFTB11", "--vault", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    assert not list(tmp_path.rglob("*.md"))


def test_command_rejects_a_ticker_that_is_not_a_fixed_income_etf():
    result = CliRunner().invoke(cli, ["etf-composition", "--ticker", "ITUB4"])

    assert result.exit_code != 0
    assert "não é um ETF de renda fixa" in result.output


def test_command_reports_a_cda_failure(monkeypatch):
    def boom(cnpj):
        raise CdaError("sem CDA")

    monkeypatch.setattr("iip.portfolio.etf_composition.default_fetch_etf_cda", boom)

    result = CliRunner().invoke(cli, ["etf-composition", "--ticker", "LFTB11"])

    assert result.exit_code != 0
    assert "sem CDA" in result.output
