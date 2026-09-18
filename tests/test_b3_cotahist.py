import io
import zipfile

from iip.sources.b3_cotahist import build_target, parse_cotahist_lines
from iip.sources.b3_cotahist_harvester import B3CotahistHTTPHarvester


def _record(
    ticker: str,
    date: str,  # YYYYMMDD
    *,
    tpmerc: str = "010",
    open_: float = 34.17,
    high: float = 34.84,
    low: float = 33.16,
    avg: float = 33.57,
    close: float = 33.50,
    trades: int = 1954,
    volume: float = 10746164.00,
) -> str:
    def money(value: float) -> str:
        return f"{round(value * 100):013d}"

    return (
        "01"
        + date
        + "02"
        + f"{ticker:<12}"
        + tpmerc
        + f"{'NOME TESTE':<12}"
        + f"{'ON':<10}"
        + "   "
        + "R$  "
        + money(open_)
        + money(high)
        + money(low)
        + money(avg)
        + money(close)
        + money(close)
        + money(close)
        + f"{trades:05d}"
        + f"{0:018d}"
        + f"{round(volume * 100):018d}"
        + f"{0:013d}"
        + "0"
        + "99991231"
        + f"{1:07d}"
        + f"{0:013d}"
        + f"{'BRTESTACNOR2':<12}"
        + "202"
    )


def test_record_helper_matches_real_field_layout():
    # Sanity check against a real line captured live from COTAHIST_A2026.ZIP
    real = (
        "012026010202LEVE3       010METAL LEVE  ON      NM   R$  000000"
        "00034170000000003484000000000331600000000033570000000003350000"
        "00000033470000000003350019540000000000003201000000000010746164"
        "00000000000000009999123100000010000000000000BRLEVEACNOR2202"
    )
    assert len(real) == 245
    parsed = parse_cotahist_lines([real])
    assert len(parsed) == 1
    quote = parsed[0]
    assert quote.ticker == "LEVE3"
    assert quote.date == "2026-01-02"
    assert quote.close == 33.50
    assert quote.high == 34.84
    assert quote.low == 33.16
    assert quote.open == 34.17
    assert quote.trades == 1954


def test_parse_filters_by_ticker_and_spot_market():
    lines = [
        _record("BBSE3", "20260917", close=40.41),
        _record("BBSE3", "20261018", tpmerc="020"),  # forward market, excluded
        _record("PETR4", "20260917", close=38.00),
    ]
    quotes = parse_cotahist_lines(lines, tickers=frozenset({"BBSE3"}))

    assert len(quotes) == 1
    assert quotes[0].ticker == "BBSE3"
    assert quotes[0].close == 40.41


def test_parse_skips_short_or_non_quote_lines():
    lines = ["00 header line", "short", _record("BBSE3", "20260917")]
    quotes = parse_cotahist_lines(lines)
    assert len(quotes) == 1


def test_build_target_rejects_years_before_1986():
    try:
        build_target(1985)
        assert False, "expected ValueError"
    except ValueError:
        pass


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A2026.ZIP"


def _fake_zip(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("COTAHIST_A2026.TXT", "\n".join(lines))
    return buffer.getvalue()


def test_harvester_downloads_extracts_and_filters():
    body = _fake_zip([_record("BBSE3", "20260917", close=40.41), _record("PETR4", "20260917")])

    def fake_opener(request, timeout):
        assert "COTAHIST_A2026" in request.full_url
        return _FakeResponse(body)

    harvester = B3CotahistHTTPHarvester(opener=fake_opener)
    result = harvester.fetch(build_target(2026), tickers=frozenset({"BBSE3"}))

    assert result.status_code == 200
    assert len(result.quotes) == 1
    assert result.quotes[0].ticker == "BBSE3"
    assert result.content_hash  # real sha256 of the downloaded body, not fabricated
