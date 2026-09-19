"""CPFL Energia (CPFE3) investor-relations documents.

ri.cpfl.com.br runs a legacy ASP.NET IR CMS: pages are addressed by an ENCRYPTED
``idCanal`` query value and every file is served by ``Download.aspx?Arquivo=<opaque
token>``. Earlier recorded as "proprietary idCanal-encoded CMS, not MZIQ" (the
"mziq" substring in the HTML is a fragment of a base64 token, not a platform
reference); the documents themselves turned out to be reachable with plain HTTP:

  - ``listresultados.aspx?idCanal=...&Center=...`` (the "Central de Resultados" of
    CPFL Energia, the listed company) returns EVERY year in one page -- 25 tables,
    each inside a container carrying ``ano="YYYY"`` -- with one row per document type
    ("Release de Resultados", "Apresentação de Resultados", audio, video, transcript,
    regulatory statements) and one link per quarter.
  - each link's ``id`` encodes type and quarter (``linkArq_Release1T_0`` = 1T release);
    the ``Download.aspx`` response is the real file (confirmed live: ``application/pdf``,
    a 3.3 MB 1T26 press release, filename in ``Content-Disposition``).

The ``idCanal``/``Center`` values are the site's own stable identifiers copied from its
navigation (they are not secrets); the group's OTHER companies (Geração, Paulista, ...)
are separate ``Center`` values and are deliberately not included -- CPFE3 is CPFL Energia.

Same request/response split as the other sources: this module builds the target and
parses the response; the transport is ``.cpfl_ri_harvester``.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from urllib.parse import urljoin

BASE_URL = "https://ri.cpfl.com.br/"
RESULTS_PATH = "listresultados.aspx?idCanal=UBKZ7EE26ff9gbUxPlf7PA==&Center=42oT3/ifbpalbl7BWgdJvg=="
RESULTS_URL = BASE_URL + RESULTS_PATH

# Categories whose files are audio/video: kept in the listing, skipped by default when
# collecting (heavy, and not textual evidence).
_MEDIA_MARKERS = ("audio", "áudio", "video", "vídeo")

_YEAR_BLOCK_RE = re.compile(r'ulAno_\d+"[^>]*?\bano="(\d{4})"')
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
# The label cell carries extra classes on some rows ("tituloCentral tituloDF" on the
# financial-statements row), so match the class prefix, not the whole attribute.
_LABEL_RE = re.compile(
    r'<td class="tituloCentral[^"]*">(.*?)</td>', re.DOTALL | re.IGNORECASE
)
_LINK_RE = re.compile(
    r'<a[^>]*href="(Download\.aspx\?Arquivo=[^"]+)"[^>]*?id="[^"]*linkArq_[A-Za-z]+?(?:(\d)T)?_\d+"',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CpflTarget:
    ticker: str
    url: str


@dataclass(frozen=True)
class CpflDocument:
    ticker: str
    year: int
    quarter: int | None
    category: str
    title: str
    url: str

    @property
    def is_media(self) -> bool:
        return any(marker in self.category.lower() for marker in _MEDIA_MARKERS)


def build_results_target(ticker: str) -> CpflTarget:
    if ticker.strip().upper() != "CPFE3":
        raise ValueError(f"no CPFL IR config for ticker {ticker!r} (only CPFE3)")
    return CpflTarget(ticker="CPFE3", url=RESULTS_URL)


def _clean(text: str) -> str:
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def parse_results_page(html: str, ticker: str = "CPFE3") -> tuple[CpflDocument, ...]:
    """Every document linked from the results center, newest year first. A link is
    attributed to the year of the ``ano="YYYY"`` container it sits in and to the row
    label of its own table row; its quarter comes from the link's ``id`` (annual
    documents, without one, get ``quarter=None``). Duplicate URLs are dropped."""
    markers = [(m.start(), int(m.group(1))) for m in _YEAR_BLOCK_RE.finditer(html)]
    documents: list[CpflDocument] = []
    seen: set[str] = set()
    for index, (start, year) in enumerate(markers):
        end = markers[index + 1][0] if index + 1 < len(markers) else len(html)
        for row in _ROW_RE.findall(html[start:end]):
            label_match = _LABEL_RE.search(row)
            if label_match is None:
                continue
            category = _clean(label_match.group(1))
            for href, quarter in _LINK_RE.findall(row):
                url = urljoin(BASE_URL, href)
                if url in seen:
                    continue
                seen.add(url)
                q = int(quarter) if quarter else None
                title = (
                    f"{category} {q}T{year % 100:02d}" if q else f"{category} {year}"
                )
                documents.append(
                    CpflDocument(
                        ticker=ticker,
                        year=year,
                        quarter=q,
                        category=category,
                        title=title,
                        url=url,
                    )
                )
    documents.sort(key=lambda d: (d.year, d.quarter or 0), reverse=True)
    return tuple(documents)
