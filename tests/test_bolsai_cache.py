import io
import json
from datetime import date
from urllib.error import HTTPError

import pytest

from iip.cli.fetch_template import fetch_fii_template_live
from iip.config import IIPSettings
from iip.portfolio.batch_value import value_portfolio
from iip.portfolio.registry import PortfolioAsset
from iip.sources.b3_bolsai import BolsaiFiiData, build_fii_target, build_target
from iip.sources.b3_bolsai_harvester import (
    BolsaiHTTPHarvester,
    BolsaiRateLimitError,
    FetchedFii,
)
from iip.sources.cvm_fii import FiiComplemento
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester, FetchedFiiReport
from iip.sources.tesouro_direto import NtnbRate

FII_BODY = json.dumps({
    "ticker": "BTLG11", "close_price": 99.78, "book_value_per_share": 106.86,
    "dividend_yield_ttm": 10.82, "reference_date": "2026-07-01",
}).encode()


class _Response:
    def __init__(self, body=FII_BODY, status=200):
        self.status = status
        self.headers = {"Content-Type": "application/json"}
        self._body = body

    def read(self):
        return self._body


class _Opener:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or _Response()

    def __call__(self, request, timeout):
        self.calls.append(request.full_url)
        return self.response


class _Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def _harvester(opener, tmp_path=None, ttl=3600.0, clock=None):
    return BolsaiHTTPHarvester(
        "secret-key-123", opener,
        cache_dir=tmp_path, cache_ttl_seconds=ttl if tmp_path else 0.0,
        clock=clock or _Clock(),
    )


# --- cache -----------------------------------------------------------------------------


def test_without_a_cache_every_call_hits_the_provider(tmp_path):
    opener = _Opener()
    harvester = _harvester(opener)

    harvester.fetch_fii(build_fii_target("BTLG11"))
    harvester.fetch_fii(build_fii_target("BTLG11"))

    assert len(opener.calls) == 2


def test_a_fresh_cached_response_is_served_without_spending_a_call(tmp_path):
    opener = _Opener()
    harvester = _harvester(opener, tmp_path)

    first = harvester.fetch_fii(build_fii_target("BTLG11"))
    second = harvester.fetch_fii(build_fii_target("BTLG11"))

    assert len(opener.calls) == 1
    assert (harvester.cache_hits, harvester.cache_misses) == (1, 1)
    assert second.fii == first.fii and second.fii.close_price == 99.78


def test_the_cache_works_across_harvester_instances_and_endpoints(tmp_path):
    opener = _Opener()
    _harvester(opener, tmp_path).fetch_fii(build_fii_target("BTLG11"))

    later = _harvester(opener, tmp_path)  # a new run
    later.fetch_fii(build_fii_target("BTLG11"))  # hit
    later.fetch_fii(build_fii_target("HGRU11"))  # different fund: miss
    later.fetch(build_target("KLBN4"))  # different endpoint (stocks): miss

    assert len(opener.calls) == 3


def test_an_entry_older_than_the_ttl_is_refetched_and_replaced(tmp_path):
    clock = _Clock()
    opener = _Opener()
    harvester = _harvester(opener, tmp_path, ttl=600.0, clock=clock)

    harvester.fetch_fii(build_fii_target("BTLG11"))
    clock.now += 599
    harvester.fetch_fii(build_fii_target("BTLG11"))  # still fresh
    clock.now += 2
    harvester.fetch_fii(build_fii_target("BTLG11"))  # expired -> refetch
    harvester.fetch_fii(build_fii_target("BTLG11"))  # the refetch is cached again

    assert len(opener.calls) == 2


def test_the_api_key_is_never_written_to_the_cache(tmp_path):
    _harvester(_Opener(), tmp_path).fetch_fii(build_fii_target("BTLG11"))

    contents = "".join(p.read_text(encoding="utf-8") for p in tmp_path.iterdir())

    assert "secret-key-123" not in contents
    assert "BTLG11" in contents  # the URL/body are


def test_only_valid_json_200_responses_are_cached(tmp_path):
    bad = _Opener(_Response(body=b"<html>not json</html>"))
    harvester = _harvester(bad, tmp_path)
    with pytest.raises(ValueError):
        harvester.fetch_fii(build_fii_target("BTLG11"))
    assert list(tmp_path.glob("*.json")) == []


def test_a_damaged_cache_entry_is_a_miss_and_gets_repaired(tmp_path):
    opener = _Opener()
    harvester = _harvester(opener, tmp_path)
    harvester.fetch_fii(build_fii_target("BTLG11"))
    entry = next(tmp_path.glob("*.json"))
    entry.write_text("{ broken", encoding="utf-8")

    result = harvester.fetch_fii(build_fii_target("BTLG11"))

    assert result.fii.close_price == 99.78 and len(opener.calls) == 2
    json.loads(entry.read_text(encoding="utf-8"))  # repaired: valid again


def test_a_cache_directory_that_cannot_be_written_never_fails_the_fetch(tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")  # a FILE where the directory should go
    harvester = _harvester(_Opener(), blocker)

    assert harvester.fetch_fii(build_fii_target("BTLG11")).fii.close_price == 99.78


def test_settings_enable_the_cache_when_no_arguments_are_given(tmp_path, monkeypatch):
    monkeypatch.setattr(
        BolsaiHTTPHarvester, "_cache_from_settings", staticmethod(lambda: (tmp_path, 3600.0))
    )
    opener = _Opener()
    harvester = BolsaiHTTPHarvester("k", opener)

    harvester.fetch_fii(build_fii_target("BTLG11"))
    harvester.fetch_fii(build_fii_target("BTLG11"))

    assert len(opener.calls) == 1


def test_the_cache_is_off_by_default_in_the_settings():
    settings = IIPSettings(_env_file=None)

    assert settings.bolsai_cache_dir is None and settings.bolsai_cache_ttl_minutes == 0


def test_a_zero_ttl_disables_the_cache_even_with_a_directory(tmp_path):
    opener = _Opener()
    harvester = BolsaiHTTPHarvester("k", opener, cache_dir=tmp_path, cache_ttl_seconds=0.0)

    harvester.fetch_fii(build_fii_target("BTLG11"))
    harvester.fetch_fii(build_fii_target("BTLG11"))

    assert len(opener.calls) == 2 and list(tmp_path.iterdir()) == []


# --- rate limit ------------------------------------------------------------------------


def _http_error(code, body):
    return HTTPError("https://api.usebolsai.com/x", code, "err", {}, io.BytesIO(body))


def test_a_429_becomes_a_legible_rate_limit_error():
    def opener(request, timeout):
        raise _http_error(
            429, b'{"error":"Rate limit exceeded","used":210,"limit":200,"tier":"free","resets":"midnight UTC"}'
        )

    with pytest.raises(BolsaiRateLimitError) as info:
        BolsaiHTTPHarvester("k", opener).fetch_fii(build_fii_target("BTLG11"))

    message = str(info.value)
    assert "210/200" in message and "midnight UTC" in message and "limite diário" in message


def test_a_429_with_an_unreadable_body_still_gives_a_clear_message():
    def opener(request, timeout):
        raise _http_error(429, b"<html>busy</html>")

    with pytest.raises(BolsaiRateLimitError, match="429"):
        BolsaiHTTPHarvester("k", opener).fetch_fii(build_fii_target("BTLG11"))


def test_other_http_errors_are_not_rewritten():
    def opener(request, timeout):
        raise _http_error(401, b"nope")

    with pytest.raises(HTTPError) as info:
        BolsaiHTTPHarvester("k", opener).fetch_fii(build_fii_target("BTLG11"))

    assert info.value.code == 401


def test_a_rate_limited_call_is_never_cached(tmp_path):
    def opener(request, timeout):
        raise _http_error(429, b'{"used":210,"limit":200}')

    harvester = BolsaiHTTPHarvester("k", opener, cache_dir=tmp_path, cache_ttl_seconds=3600.0)
    with pytest.raises(BolsaiRateLimitError):
        harvester.fetch_fii(build_fii_target("BTLG11"))

    assert list(tmp_path.iterdir()) == []


# --- analysis-only inputs can be skipped -----------------------------------------------

CNPJ = "11.839.593/0001-09"


def _mock_fii_world(monkeypatch):
    complementos = tuple(
        FiiComplemento(
            cnpj_fundo_classe=CNPJ, data_referencia=f"2026-0{m}-01", versao="1",
            valores={"Valor_Patrimonial_Cotas": 97.4, "Cotas_Emitidas": 10_000_000,
                     "Patrimonio_Liquido": 1e9, "Percentual_Dividend_Yield_Mes": 0.01},
        )
        for m in range(1, 8)
    )
    monkeypatch.setattr(
        CvmFiiHTTPHarvester, "fetch",
        lambda self, target: FetchedFiiReport(
            target=target, status_code=200, geral=(), ativo_passivo=(), complemento=complementos
        ),
    )
    monkeypatch.setattr(
        BolsaiHTTPHarvester, "fetch_fii",
        lambda self, target: FetchedFii(
            target=target, status_code=200,
            fii=BolsaiFiiData(
                ticker="HGCR11", name="X", reference_date="2026-07-01", close_price=95.45,
                book_value_per_share=97.4, pvp=0.98, dividend_yield_ttm=12.31,
                net_asset_value=None, shares_outstanding=None, total_shareholders=None,
                segment=None, management_type=None,
            ),
        ),
    )


def test_valuation_only_fetch_skips_the_analyzer_inputs_but_keeps_the_valuation_ones(monkeypatch):
    import iip.cli.fetch_template as ft

    _mock_fii_world(monkeypatch)

    def must_not_run(*args, **kwargs):
        raise AssertionError("analyzer-only input was fetched")

    monkeypatch.setattr(ft, "_enrich_fii_with_patria_fundamentos", must_not_run)
    monkeypatch.setattr(ft, "_fii_dividend_pillar_inputs", must_not_run)

    template, result = fetch_fii_template_live("HGCR11", CNPJ, 2026, "k", analysis_inputs=False)

    fin = template["financials"]
    assert template["price"] == 95.45
    assert fin["nav_per_share"] == 97.4 and fin["dividend_per_share"] == pytest.approx(11.99, abs=0.01)
    assert "nav_change_12m_pct" not in fin
    assert fin.get("risk_free_real_yield") is None  # the analyzer default (None), not fetched
    assert "risk_free_real_yield" not in result.fetched_fields


def test_the_default_still_fetches_the_analyzer_inputs(monkeypatch):
    import iip.cli.fetch_template as ft

    _mock_fii_world(monkeypatch)
    calls = []
    monkeypatch.setattr(
        ft, "_enrich_fii_with_patria_fundamentos",
        lambda financials, symbol: (calls.append("patria") or financials, [], []),
    )

    fetch_fii_template_live("HGCR11", CNPJ, 2026, "k")

    assert calls == ["patria"]


def test_value_portfolio_asks_for_the_valuation_only_template(monkeypatch):
    import iip.cli.fetch_template as ft

    seen = []

    def recorder(symbol, cnpj, ano, key, **kwargs):
        seen.append(kwargs)
        return {"price": 99.78, "financials": {"nav_per_share": 106.86}}, object()

    monkeypatch.setattr(ft, "fetch_fii_template_live", recorder)
    fii = PortfolioAsset("BTLG11", "fund", subtype="FII", structure="Tijolo", segment="Logístico",
                         cnpj="00.000.000/0000-00")

    result = value_portfolio(
        bolsai_api_key="k", brapi_token=None, positions=(fii,),
        fetch_rate=lambda: NtnbRate(date(2026, 9, 17), date(2060, 8, 15), 0.073),
    )

    assert seen == [{"analysis_inputs": False}]
    assert result.outcomes[0].status == "ok"
