"""CVM FIAGRO Informe Mensal — official open-data channel.

Same rationale as ``iip.sources.cvm_fii``: official CVM open data
(dados.cvm.gov.br), no login, no JS. Structure verified directly
against a real downloaded file (inf_mensal_fiagro_202508.zip), not
assumed — and it differs from FII's in two important ways:

1. **Publication cadence**: FIAGRO ZIPs are published *monthly*
   (``inf_mensal_fiagro_{AAAAMM}.zip``, e.g. ``inf_mensal_fiagro_202508.zip``),
   not yearly like FII's (``inf_mensal_fii_{AAAA}.zip``). Only the last
   ~12 months are kept available.
2. **File layout**: FIAGRO ships ONE combined file (133 columns —
   identity, shareholder composition, and full balance sheet all in a
   single row per fund per month) plus a small subclass-level file,
   rather than FII's three separate geral/ativo_passivo/complemento
   files. Join key: ``CNPJ_Classe`` + ``Data_Referencia`` (+ ``Versao``).

Given the ~115 non-identity numeric columns (Numero_Cotistas through
Total_Passivo), they are exposed as a ``valores: dict[str, float | None]``
keyed by CVM's own column names, the same tradeoff already made for
FII's ativo_passivo/complemento — 115 hand-typed fields would be a
high typo risk for little benefit over a dict lookup by the CVM's own
documented name.

Files are ';'-delimited, Latin-1 (ISO-8859-1) encoded, CRLF line
endings — same CVM convention as FII.

Same request/response split as the other sources: this module builds
the request URL and parses the response; it performs no HTTP request
itself (see ``.cvm_fiagro_harvester`` for the transport).
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field

BASE_URL = "https://dados.cvm.gov.br/dados/FIAGRO/DOC/INF_MENSAL/DADOS"


@dataclass(frozen=True)
class CvmFiagroTarget:
    ano: int
    mes: int
    url: str


@dataclass(frozen=True)
class FiagroInforme:
    cnpj_classe: str
    nome_classe: str | None
    data_referencia: str
    versao: str
    nome_administrador: str | None
    cnpj_administrador: str | None
    nome_gestor: str | None
    cnpj_gestor: str | None
    mercado_negociacao: str | None
    codigo_isin: str | None
    valores: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class FiagroSubclasse:
    cnpj_classe: str
    nome_classe: str | None
    data_referencia: str
    nome_subclasse: str | None
    numero_cotas: float | None
    valor_patrimonial_cota: float | None


def build_target(ano: int, mes: int) -> CvmFiagroTarget:
    """Build the request URL for a given competência (year+month)."""

    if not (1 <= mes <= 12):
        raise ValueError(f"mes must be between 1 and 12, got {mes}")
    if ano < 2022:
        raise ValueError("CVM's FIAGRO structured report starts in 2022")

    competencia = f"{ano:04d}{mes:02d}"
    url = f"{BASE_URL}/inf_mensal_fiagro_{competencia}.zip"
    return CvmFiagroTarget(ano=ano, mes=mes, url=url)


def _parse_number(raw: str) -> float | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _read_csv_rows(archive: zipfile.ZipFile, filename_fragment: str, *, exclude: str | None = None) -> list[dict[str, str]]:
    matches = [
        name
        for name in archive.namelist()
        if filename_fragment in name and (exclude is None or exclude not in name)
    ]
    if not matches:
        return []
    with archive.open(matches[0]) as raw:
        text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
        reader = csv.DictReader(text, delimiter=";")
        return list(reader)


_IDENTITY_FIELDS = {
    "cnpj_classe": "CNPJ_Classe",
    "nome_classe": "Nome_Classe",
    "data_referencia": "Data_Referencia",
    "versao": "Versao",
    "nome_administrador": "Nome_Administrador",
    "cnpj_administrador": "CNPJ_Administrador",
    "nome_gestor": "Nome_Gestor",
    "cnpj_gestor": "CNPJ_Gestor",
    "mercado_negociacao": "Mercado_Negociacao",
    "codigo_isin": "Codigo_ISIN",
}
_IDENTITY_COLUMNS = set(_IDENTITY_FIELDS.values())


def parse_informe(body: bytes) -> tuple[FiagroInforme, ...]:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = _read_csv_rows(archive, "inf_mensal_fiagro_", exclude="subclasse")

    results = []
    for row in rows:
        known = {k: (row.get(v) or None) for k, v in _IDENTITY_FIELDS.items()}
        # cnpj_classe/data_referencia/versao must not silently become None
        known["cnpj_classe"] = row.get("CNPJ_Classe", "")
        known["data_referencia"] = row.get("Data_Referencia", "")
        known["versao"] = row.get("Versao", "")
        valores = {
            k: _parse_number(v) for k, v in row.items() if k not in _IDENTITY_COLUMNS
        }
        results.append(FiagroInforme(**known, valores=valores))
    return tuple(results)


def parse_subclasse(body: bytes) -> tuple[FiagroSubclasse, ...]:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = _read_csv_rows(archive, "_subclasse_")

    results = []
    for row in rows:
        results.append(
            FiagroSubclasse(
                cnpj_classe=row.get("CNPJ_Classe", ""),
                nome_classe=row.get("Nome_Classe") or None,
                data_referencia=row.get("Data_Referencia", ""),
                nome_subclasse=row.get("Nome_Subclasse") or None,
                numero_cotas=_parse_number(row.get("Numero_Cotas", "")),
                valor_patrimonial_cota=_parse_number(
                    row.get("Valor_Patrimonial_Cota", "")
                ),
            )
        )
    return tuple(results)
