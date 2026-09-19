import json
from typing import ClassVar

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.solutions_ir import (
    SOLUTIONS_IR_COMPANIES,
    build_documents_target,
    build_site_targets,
    company_for_ticker,
    parse_documents_response,
)
from iip.sources.solutions_ir_harvester import SolutionsIrHTTPHarvester

SITE = "cda8bfad-7383-4b57-bede-6ce1af8a28ba"


def _payload(year, *, extra=None):
    docs = {
        "press_release": [
            {"id": f"pr-{year}", "title": f"Release 2T{year % 100}", "name": "",
             "url": f"https://cdn.example/{year}/release.pdf",
             "refDate": f"{year}-06-30T03:00:00Z", "deliveryDate": f"{year}-08-07T03:00:00Z"},
        ],
        "audio": [
            {"id": f"au-{year}", "title": "Áudio do webcast", "name": "",
             "url": f"https://cdn.example/{year}/webcast.mp3",
             "refDate": f"{year}-06-30T03:00:00Z", "deliveryDate": f"{year}-08-08T03:00:00Z"},
        ],
        "assembleia": [{"id": "x", "title": "sem link", "url": "", "refDate": f"{year}-01-01T00:00:00Z"}],
    }
    docs.update(extra or {})
    return {
        "years": [f"{year}-01-02T00:00:00Z"],
        "categoriesTitle": {"press_release": "Release de Resultados ", "audio": "Áudio"},
        "categories": docs,
    }


# --- registry and targets ------------------------------------------------------------------


def test_csud3_is_registered_as_a_company_site():
    company = company_for_ticker("csud3")

    assert company.is_site and company.site_id == SITE
    assert not company_for_ticker("BTCI11").is_site
    assert set(SOLUTIONS_IR_COMPANIES) == {"BTCI11", "CSUD3"}


def test_one_target_per_year_using_the_date_parameter_the_real_site_uses():
    targets = build_site_targets("CSUD3", (2026, 2025))

    assert [t.url for t in targets] == [
        f"https://api.solutions-ir.com/v2/files/{SITE}?language=pt&date=2026-01-02",
        f"https://api.solutions-ir.com/v2/files/{SITE}?language=pt&date=2025-01-02",
    ]
    assert all(t.ticker == "CSUD3" for t in targets)


def test_the_two_endpoint_shapes_are_not_mixed_up():
    with pytest.raises(ValueError, match="company site"):
        build_documents_target("CSUD3")
    with pytest.raises(ValueError, match="fund endpoint"):
        build_site_targets("BTCI11", (2026,))
    with pytest.raises(ValueError, match="no Solutions IR config"):
        build_site_targets("ALZR11", (2026,))


# --- parsing --------------------------------------------------------------------------------


def test_the_company_response_is_parsed_into_documents():
    documents = parse_documents_response(json.dumps(_payload(2026)).encode(), "CSUD3")

    release = next(d for d in documents if d.category_sigla == "press_release")
    assert release.category_name == "Release de Resultados"  # title trimmed
    assert release.year == "2026"
    assert release.date == "2026-08-07"  # the delivery date
    assert release.title == "Release 2T26"
    assert release.url == "https://cdn.example/2026/release.pdf"


def test_documents_without_a_link_are_dropped():
    documents = parse_documents_response(json.dumps(_payload(2026)).encode(), "CSUD3")

    assert {d.category_sigla for d in documents} == {"press_release", "audio"}


def test_a_category_without_a_title_falls_back_to_its_key():
    payload = _payload(2026, extra={"politicas": [
        {"id": "p", "title": "Política X", "url": "https://cdn.example/p.pdf",
         "refDate": "2026-03-01T00:00:00Z", "deliveryDate": "2026-03-01T00:00:00Z"}]})

    documents = parse_documents_response(json.dumps(payload).encode(), "CSUD3")

    assert next(d for d in documents if d.category_sigla == "politicas").category_name == "politicas"


def test_the_fund_response_shape_still_parses_as_before():
    fund = {"files": [{"sigla": "RM", "nome_tipo": "RELATORIO MENSAL", "ano_historico": [
        {"ano": "2026", "historico": [{"link": "https://x/a.pdf", "nome": "Jul", "data_descricao": "jul"}]}]}]}

    documents = parse_documents_response(json.dumps(fund).encode(), "BTCI11")

    assert [(d.category_sigla, d.year, d.title) for d in documents] == [("RM", "2026", "Jul")]


# --- harvesting -----------------------------------------------------------------------------


class _Response:
    status = 200

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body


def _harvester(calls):
    def opener(request, timeout):
        url = request.full_url
        calls.append(url)
        year = int(url.split("date=")[1][:4])
        return _Response(json.dumps(_payload(year)).encode())

    return SolutionsIrHTTPHarvester(opener)


def test_collect_merges_the_requested_years_newest_first():
    calls = []

    documents = _harvester(calls).collect("CSUD3", years=(2026, 2025, 2024))

    assert len(calls) == 3
    releases = [d for d in documents if d.category_sigla == "press_release"]
    assert [d.year for d in releases] == ["2026", "2025", "2024"]


def test_collect_deduplicates_the_same_document_across_years():
    def opener(request, timeout):
        return _Response(json.dumps(_payload(2026)).encode())  # every call returns 2026

    documents = SolutionsIrHTTPHarvester(opener).collect("CSUD3", years=(2026, 2025))

    assert len([d for d in documents if d.category_sigla == "press_release"]) == 1


def test_collect_for_a_company_requires_years_and_for_a_fund_ignores_them():
    with pytest.raises(ValueError, match="years is required"):
        _harvester([]).collect("CSUD3")

    fund = {"files": [{"sigla": "RM", "nome_tipo": "R", "ano_historico": [
        {"ano": "2026", "historico": [{"link": "https://x/a.pdf", "nome": "Jul"}]}]}]}
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        return _Response(json.dumps(fund).encode())

    documents = SolutionsIrHTTPHarvester(opener).collect("BTCI11", years=(2026, 2025))

    assert len(calls) == 1 and "/v2/asset/" in calls[0] and len(documents) == 1


# --- CLI ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _run_cli(monkeypatch, tmp_path, *extra):
    import urllib.request

    docs = parse_documents_response(json.dumps(_payload(2026)).encode(), "CSUD3")
    monkeypatch.setattr(SolutionsIrHTTPHarvester, "collect", lambda self, ticker, years: docs)
    downloaded = []

    class _Resp:
        headers: ClassVar[dict] = {"Content-Type": "application/pdf"}

        def __init__(self, url):
            self._url = url

        def read(self):
            return b"%PDF-1.4 " + self._url.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout=None):
        downloaded.append(request.full_url)
        return _Resp(request.full_url)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = CliRunner().invoke(
        cli,
        ["collect-solutions-ir-documents", "--ticker", "CSUD3", "--sem-evidencia",
         "--vault", str(tmp_path), *extra],
    )
    return result, downloaded


def test_the_cli_skips_audio_and_video_by_default(monkeypatch, tmp_path):
    result, downloaded = _run_cli(monkeypatch, tmp_path)

    assert result.exit_code == 0, result.output
    assert downloaded == ["https://cdn.example/2026/release.pdf"]


def test_the_cli_includes_media_on_request(monkeypatch, tmp_path):
    result, downloaded = _run_cli(monkeypatch, tmp_path, "--incluir-midia")

    assert result.exit_code == 0, result.output
    assert sorted(downloaded) == [
        "https://cdn.example/2026/release.pdf", "https://cdn.example/2026/webcast.mp3",
    ]


def test_the_cli_passes_the_history_window_as_calendar_years(monkeypatch, tmp_path):
    seen = {}
    import datetime as dt

    monkeypatch.setattr(
        SolutionsIrHTTPHarvester, "collect",
        lambda self, ticker, years: seen.setdefault("years", years) and (),
    )
    result = CliRunner().invoke(
        cli,
        ["collect-solutions-ir-documents", "--ticker", "CSUD3", "--sem-evidencia",
         "--vault", str(tmp_path), "--anos-historico", "2"],
    )

    year = dt.date.today().year  # noqa: DTZ011
    assert result.exit_code == 0, result.output
    assert seen["years"] == (year, year - 1)
