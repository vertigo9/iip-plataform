import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.static_pdf_listing import (
    STATIC_PDF_LISTING_FUNDS,
    build_targets,
    fund_for_ticker,
    parse_pdf_links,
)
from iip.sources.static_pdf_listing_harvester import StaticPdfListingHTTPHarvester

CENTRAL = "https://ri.isaenergiabrasil.com.br/pt/informacoes-financeiras/central-de-resultados"

PAGE_2026 = """
<a href="/pt/documentos/6574-Earnings-Release-1T26.pdf">Release</a>
<a href="/pt/documentos/6576-Resultados-Excel-1T26.xlsx">Excel</a>
<a href="/pt/documentos/6900-Audio-Webcast.mp3">Audio</a>
<a href="/pt/documentos/6574-Earnings-Release-1T26.pdf">Release (dup)</a>
"""


# --- registration ---------------------------------------------------------------------------


def test_the_seven_funds_and_the_isae4_cmig4_companies_are_registered():
    assert set(STATIC_PDF_LISTING_FUNDS) == {
        "TRXF11", "VGIP11", "CPTI11", "MANA11", "RBVA11", "HGBS11", "KNRI11", "ISAE4", "CMIG4",
    }


def test_fund_registrations_keep_their_old_behaviour():
    for ticker in ("TRXF11", "VGIP11", "CPTI11", "MANA11", "RBVA11", "HGBS11", "KNRI11"):
        fund = fund_for_ticker(ticker)
        assert fund.year_param is None and fund.extra_page_urls == ()
        assert fund.extensions == (".pdf",)
        assert build_targets(ticker, (2026, 2025)) == build_targets(ticker)  # years ignored
        assert len(build_targets(ticker)) == 1


def test_isae4_reads_the_results_center_by_year_and_three_more_pages():
    fund = fund_for_ticker("ISAE4")

    assert fund.page_url == CENTRAL
    assert fund.year_param == "ano" and fund.extensions == (".pdf", ".xlsx")
    assert len(fund.extra_page_urls) == 3


# --- targets --------------------------------------------------------------------------------


def test_one_results_page_per_year_then_the_extra_pages():
    urls = [t.url for t in build_targets("ISAE4", (2026, 2025))]

    assert urls[:2] == [f"{CENTRAL}?ano=2026", f"{CENTRAL}?ano=2025"]
    assert len(urls) == 5 and urls[2].endswith("/relatorios")
    assert all(t.ticker == "ISAE4" for t in build_targets("ISAE4", (2026,)))


def test_without_years_the_main_page_is_read_once():
    urls = [t.url for t in build_targets("ISAE4")]

    assert urls[0] == CENTRAL and len(urls) == 4


def test_an_unregistered_ticker_is_refused():
    with pytest.raises(ValueError, match="no static-listing config"):
        build_targets("ALZR11")


# --- parsing --------------------------------------------------------------------------------


def test_xlsx_links_are_kept_only_when_the_registration_asks_for_them():
    default = parse_pdf_links(PAGE_2026, CENTRAL, "ISAE4")
    with_xlsx = parse_pdf_links(PAGE_2026, CENTRAL, "ISAE4", (".pdf", ".xlsx"))

    assert [d.url.rsplit(".", 1)[-1] for d in default] == ["pdf"]
    assert sorted(d.url.rsplit(".", 1)[-1] for d in with_xlsx) == ["pdf", "xlsx"]  # mp3 never


def test_relative_links_resolve_against_the_page_and_are_deduplicated():
    documents = parse_pdf_links(PAGE_2026, CENTRAL, "ISAE4", (".pdf", ".xlsx"))

    assert len(documents) == 2
    assert documents[0].url == "https://ri.isaenergiabrasil.com.br/pt/documentos/6574-Earnings-Release-1T26.pdf"


def test_titles_drop_the_extension_for_both_kinds():
    titles = {d.title for d in parse_pdf_links(PAGE_2026, CENTRAL, "ISAE4", (".pdf", ".xlsx"))}

    assert titles == {"6574 Earnings Release 1T26", "6576 Resultados Excel 1T26"}


# --- harvesting -----------------------------------------------------------------------------


class _Response:
    status = 200

    def __init__(self, body, url):
        self._body = body.encode()
        self._url = url

    def read(self):
        return self._body

    def geturl(self):
        return self._url


def _opener(pages, calls=None):
    def opener(request, timeout):
        url = request.full_url
        if calls is not None:
            calls.append(url)
        body = pages[url]
        if isinstance(body, Exception):
            raise body
        return _Response(body, url)

    return opener


def _page(name):
    return f'<a href="/pt/documentos/{name}.pdf">x</a>'


def test_collect_merges_years_and_pages_deduplicating_by_url():
    pages = {
        f"{CENTRAL}?ano=2026": _page("A-2026") + _page("SHARED"),
        f"{CENTRAL}?ano=2025": _page("A-2025") + _page("SHARED"),
    }
    for extra in fund_for_ticker("ISAE4").extra_page_urls:
        pages[extra] = _page("REL-" + extra.rsplit("/", 1)[-1]) + _page("SHARED")

    documents = StaticPdfListingHTTPHarvester(_opener(pages)).collect("ISAE4", years=(2026, 2025))

    names = [d.url.rsplit("/", 1)[-1] for d in documents]
    assert names.count("SHARED.pdf") == 1
    assert {"A-2026.pdf", "A-2025.pdf", "REL-relatorios.pdf"} <= set(names)


def test_a_failing_later_page_is_recorded_and_skipped_but_the_first_page_must_succeed():
    extras = fund_for_ticker("ISAE4").extra_page_urls
    pages = {f"{CENTRAL}?ano=2026": _page("A"), extras[0]: OSError("timeout"),
             extras[1]: _page("B"), extras[2]: _page("C")}
    harvester = StaticPdfListingHTTPHarvester(_opener(pages))

    documents = harvester.collect("ISAE4", years=(2026,))

    assert {d.url.rsplit("/", 1)[-1] for d in documents} == {"A.pdf", "B.pdf", "C.pdf"}
    assert len(harvester.last_errors) == 1 and "timeout" in harvester.last_errors[0]

    broken_first = {f"{CENTRAL}?ano=2026": OSError("down")}
    with pytest.raises(OSError, match="down"):
        StaticPdfListingHTTPHarvester(_opener(broken_first)).collect("ISAE4", years=(2026,))


def test_a_fund_is_still_one_request():
    fund = fund_for_ticker("KNRI11")
    calls = []

    StaticPdfListingHTTPHarvester(_opener({fund.page_url: _page("KNRI")}, calls)).collect(
        "KNRI11", years=(2026, 2025)
    )

    assert calls == [fund.page_url]


# --- CLI ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_the_cli_accepts_isae4_and_passes_the_history_window(monkeypatch, tmp_path):
    import datetime as dt

    seen = {}

    def fake_collect(self, ticker, years):
        seen.update(ticker=ticker, years=years)
        return ()

    monkeypatch.setattr(StaticPdfListingHTTPHarvester, "collect", fake_collect)
    result = CliRunner().invoke(
        cli,
        ["collect-static-documents", "--ticker", "isae4", "--sem-evidencia",
         "--vault", str(tmp_path), "--anos-historico", "2"],
    )

    year = dt.date.today().year  # noqa: DTZ011
    assert result.exit_code == 0, result.output
    assert seen == {"ticker": "ISAE4", "years": (year, year - 1)}


def test_cmig4_reads_one_page_per_year_in_the_path() -> None:
    fund = fund_for_ticker("CMIG4")
    assert fund is not None and fund.year_in_path and fund.year_param is None

    targets = build_targets("CMIG4", years=(2026, 2025))
    urls = [t.url for t in targets]
    base = "https://ri.cemig.com.br/servicos-aos-investidores/central-de-downloads"

    assert urls[:2] == [f"{base}/2026", f"{base}/2025"]
    assert len(urls) == 2 + len(fund.extra_page_urls)
    # no years given (or a fund without the option): the plain page, once
    assert build_targets("CMIG4")[0].url == base
