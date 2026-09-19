"""CPFL Energia (CPFE3) results center: parsing, transport and the collection command."""

from __future__ import annotations

import datetime as dt
import io

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.sources.cpfl_ri import (
    RESULTS_URL,
    CpflDocument,
    build_results_target,
    parse_results_page,
)
from iip.sources.cpfl_ri_harvester import CpflRiHTTPHarvester


def _link(kind: str, quarter: int | None, index: int, token: str) -> str:
    suffix = f"{quarter}T" if quarter else ""
    return (
        f'<a href="Download.aspx?Arquivo={token}" '
        f'id="ctl00_linkArq_{kind}{suffix}_{index}">x</a>'
    )


def _row(label: str, links: str, cls: str = "tituloCentral") -> str:
    return f'<tr><td class="{cls}">{label}</td><td>{links}</td></tr>'


def _year(year: int, rows: str) -> str:
    return f'<div id="ulAno_{year}" class="x" ano="{year}"><table>{rows}</table></div>'


HTML = (
    _year(
        2026,
        _row("Release de Resultados", _link("Release", 1, 0, "r1") + _link("Release", 2, 1, "r2"))
        + _row("Apresentação de Resultados", _link("Apres", 2, 0, "a2"))
        + _row("Vídeo da Conferência", _link("Video", 2, 0, "v2"))
        + _row(
            "Demonstrações Financeiras",
            _link("DF", 2, 0, "d2"),
            cls="tituloCentral tituloDF",
        ),
    )
    + _year(
        2025,
        _row("Demonstrações Financeiras", _link("DF", None, 0, "d25"), cls="tituloCentral tituloDF")
        + _row("Release de Resultados", _link("Release", 4, 0, "r1")),  # repeated token: dropped
    )
)


class _Response(io.BytesIO):
    status = 200


def test_target_is_cpfe3_only() -> None:
    assert build_results_target("cpfe3").url == RESULTS_URL
    with pytest.raises(ValueError):
        build_results_target("ISAE4")


def test_parse_attributes_year_quarter_and_category() -> None:
    documents = parse_results_page(HTML)
    by_title = {d.title: d for d in documents}

    assert by_title["Release de Resultados 1T26"].year == 2026
    assert by_title["Release de Resultados 1T26"].quarter == 1
    assert by_title["Apresentação de Resultados 2T26"].category == "Apresentação de Resultados"
    # extra class on the label cell (financial statements) must still be picked up
    assert "Demonstrações Financeiras 2T26" in by_title
    # a link with no quarter is an annual document
    annual = by_title["Demonstrações Financeiras 2025"]
    assert annual.quarter is None and annual.year == 2025
    assert annual.url.startswith("https://ri.cpfl.com.br/Download.aspx?Arquivo=")


def test_parse_dedupes_urls_and_sorts_newest_first() -> None:
    documents = parse_results_page(HTML)
    urls = [d.url for d in documents]

    assert len(urls) == len(set(urls))
    # token "r1" appears in 2026 first, so the 2025 repeat is dropped
    assert not any(d.year == 2025 and d.category == "Release de Resultados" for d in documents)
    keys = [(d.year, d.quarter or 0) for d in documents]
    assert keys == sorted(keys, reverse=True)


def test_media_flag_covers_audio_and_video() -> None:
    def doc(category: str) -> CpflDocument:
        return CpflDocument("CPFE3", 2026, 1, category, category, "u")

    assert doc("Vídeo da Conferência").is_media
    assert doc("Conferência de Resultados (Áudio)").is_media
    assert not doc("Release de Resultados").is_media


def test_harvester_fetches_and_parses() -> None:
    seen = []

    def opener(request, timeout):
        seen.append((request.full_url, timeout))
        return _Response(HTML.encode("utf-8"))

    fetched = CpflRiHTTPHarvester(opener=opener).fetch()

    assert seen[0][0] == RESULTS_URL
    assert fetched.status_code == 200
    assert len(fetched.documents) == len(parse_results_page(HTML))


def test_cli_skips_media_and_old_years_by_default(monkeypatch, tmp_path) -> None:
    from iip.sources import cpfl_ri_harvester

    this_year = dt.date.today().year  # noqa: DTZ011 — ano de calendário, não timestamp
    html = _year(
        this_year,
        _row("Release de Resultados", _link("Release", 1, 0, "new"))
        + _row("Vídeo da Conferência", _link("Video", 1, 0, "vid")),
    ) + _year(this_year - 10, _row("Release de Resultados", _link("Release", 1, 0, "old")))

    monkeypatch.setattr(
        cpfl_ri_harvester,
        "urlopen",
        lambda request, timeout=None: _Response(html.encode("utf-8")),
    )
    downloaded: list[str] = []

    class _Download(io.BytesIO):
        headers = {"Content-Type": "application/pdf"}  # noqa: RUF012

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        downloaded.append(request.full_url)
        return _Download(b"%PDF-1.4 fake")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = CliRunner().invoke(
        cli, ["collect-cpfl-documents", "--sem-evidencia", "--vault", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    assert downloaded == ["https://ri.cpfl.com.br/Download.aspx?Arquivo=new"]
    assert "1/1" in result.output
