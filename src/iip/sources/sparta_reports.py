"""Sparta's own monthly management report (PDF) -- the only channel
found this session with a real, extractable NAV-per-quota for CRAA11
(Sparta Fiagro), whose CNPJ is confirmed absent from CVM's FIAGRO open
dataset (see ``iip.sources.cvm_fiagro``).

Unlike the Playwright-driven Patria harvester (``iip.harvest.patria``,
built for a JS-rendered MZIQ investor-relations portal), Sparta serves
its reports as plain static PDF downloads at a predictable URL -- no
browser engine needed, just an HTTP GET, same request/response split
as every other source in this project.

URL confirmed live (17/09/2026):
``https://sparta.com.br/uploads/{TICKER}_RelatorioMensal_{ano}_{mes:02d}.pdf``
(e.g. ``CRAA11_RelatorioMensal_2026_03.pdf``), available back to at
least 01/2025.

Extraction is genuinely fragile compared to every CSV/ZIP-based source
in this project: it depends on Sparta's own PDF page layout staying
the same. Confirmed live against the real March/2026 PDF using
pypdf's layout-preserving text mode -- the "DESTAQUES DO MES" section
renders as a 2-row grid where each value sits directly above its
label, e.g.::

    R$ 101,64                    R$ 1,25                 15,6%
          Cota patrimonial          Ultima distribuicao     Dividend Yield (12m)

``_extract_cota_patrimonial`` locates the "Cota patrimonial" label and
reads the number vertically aligned above it (by character column, not
by a fixed line offset) -- more robust to the other stat boxes being
reordered than an index-based read, but still assumes this general
grid shape. If Sparta redesigns the report, this will start returning
None (silently missing, never a wrong number) rather than raise --
callers should treat that as "recheck the layout", not "no data this
month".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BASE_URL = "https://sparta.com.br/uploads"

_DESTAQUES_HEADING = "DESTAQUES DO M"  # "MES"/"MÊS" -- encoding varies by extractor
_COTA_LABEL = "Cota patrimonial"
_VALUE_RE = re.compile(r"R\$\s*[\d.]+,\d{2}")


@dataclass(frozen=True)
class SpartaReportTarget:
    ticker: str
    ano: int
    mes: int
    url: str


def build_target(ticker: str, ano: int, mes: int) -> SpartaReportTarget:
    if not (1 <= mes <= 12):
        raise ValueError(f"mes must be between 1 and 12, got {mes}")
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")
    url = f"{BASE_URL}/{normalized}_RelatorioMensal_{ano:04d}_{mes:02d}.pdf"
    return SpartaReportTarget(ticker=normalized, ano=ano, mes=mes, url=url)


def _parse_brl(raw: str) -> float:
    return float(raw.replace("R$", "").strip().replace(".", "").replace(",", "."))


def _extract_cota_patrimonial_from_text(layout_text: str) -> float | None:
    """Pure text-parsing step, split out from PDF decoding so it can be
    tested directly against real captured report text without needing
    a binary PDF fixture."""
    heading_pos = layout_text.find(_DESTAQUES_HEADING)
    if heading_pos == -1:
        return None
    block = layout_text[heading_pos:]

    lines = block.splitlines()
    label_line_index = next(
        (i for i, line in enumerate(lines) if _COTA_LABEL in line), None
    )
    if label_line_index is None:
        return None
    label_column = lines[label_line_index].find(_COTA_LABEL)

    # The value sits on the nearest non-blank line above the label line.
    value_line = next(
        (
            lines[i]
            for i in range(label_line_index - 1, -1, -1)
            if lines[i].strip()
        ),
        None,
    )
    if value_line is None:
        return None

    candidates = [(m.start(), m.group()) for m in _VALUE_RE.finditer(value_line)]
    if not candidates:
        return None

    closest = min(candidates, key=lambda item: abs(item[0] - label_column))
    try:
        return _parse_brl(closest[1])
    except ValueError:
        return None


def extract_cota_patrimonial(pdf_body: bytes) -> float | None:
    """Extract "Cota patrimonial" (NAV per quota, BRL) from a Sparta
    monthly report PDF. Returns None if the layout doesn't match what
    was confirmed live (see module docstring) -- never guesses."""
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(pdf_body))
    for page in reader.pages:
        text = page.extract_text(extraction_mode="layout")
        if _DESTAQUES_HEADING in text:
            return _extract_cota_patrimonial_from_text(text)
    return None
