"""CVM FII Informe Mensal Estruturado — official open-data channel.

Audit finding: FNET's own search UI (fnet.bmfbovespa.com.br) turned out
to be built for interactive/institutional use — protected by
Cloudflare, requires a real filter selection to return any row, and
its underlying JSON endpoint would not return data even when called
from inside the loaded page's own JS context (confirmed live, several
attempts). The CVM publishes the *same* regulatory content (FII
monthly reports, filed via Fundos.NET under ANEXO 39-I da Instrução
CVM 571/2015) as plain downloadable ZIP/CSV files on its own open-data
portal (dados.cvm.gov.br, a CKAN instance) — no login, no JS, no
Cloudflare, weekly updates, history since 2016. This is the channel
this module uses instead of scraping FNET's UI.

CSV structure verified directly against a real downloaded file
(inf_mensal_fii_2026.zip), not assumed from documentation:
  - inf_mensal_fii_geral_AAAA.csv — fund identity (name, manager,
    segment, management type, address).
  - inf_mensal_fii_ativo_passivo_AAAA.csv — full balance sheet (52
    columns: liquidity, securities, real estate assets, liabilities).
  - inf_mensal_fii_complemento_AAAA.csv — shareholder composition, net
    asset value, monthly dividend yield (already computed by CVM).
All three share the same join key: CNPJ_Fundo_Classe + Data_Referencia
(+ Versao, since a fund can resubmit a given month).

Files are ';'-delimited, Latin-1 (ISO-8859-1) encoded, CRLF line
endings — the standard CVM open-data convention, confirmed on the real
file. Numeric cells can be empty strings (not zero) — parsed as
``None``, never coerced to 0.0. The ativo_passivo and complemento files
have far too many columns (52 and 30) to name individually without a
high risk of typos; their non-identity columns are exposed as a
``valores: dict[str, float | None]`` keyed by CVM's own column names,
rather than 80 hand-typed dataclass fields.

Same request/response split as the other sources: this module builds
the request URL and parses the response; it performs no HTTP request
itself (see ``.cvm_fii_harvester`` for the transport).
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field

BASE_URL = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS"
_FIRST_AVAILABLE_YEAR = 2016


@dataclass(frozen=True)
class CvmFiiTarget:
    ano: int
    url: str
    provider: str = "cvm"
    role: str = "regulatory"
    year: int | None = None
    # CVM's monthly informe is ONE file covering hundreds of funds at
    # once -- there is no single real ticker this document is "about",
    # unlike bolsai (one request per FII) or XP Asset (one document per
    # asset). "MULTI" is a deliberate, self-documenting sentinel (not
    # "" or None) so AtlasDocumentAdapter.from_fetched() -- which
    # assumes one-document-one-ticker everywhere else -- has something
    # explicit to read, without pretending this bulk file belongs to
    # any specific fund. Confirmed live in TRACE 15.13/15.13.1: the
    # adapter unconditionally reads target.ticker.
    ticker: str = "MULTI"


@dataclass(frozen=True)
class FiiGeral:
    cnpj_fundo_classe: str
    data_referencia: str
    versao: str
    tipo_fundo_classe: str | None
    nome_fundo_classe: str | None
    segmento_atuacao: str | None
    tipo_gestao: str | None
    mandato: str | None
    nome_administrador: str | None
    cnpj_administrador: str | None
    cidade: str | None
    estado: str | None
    outros_campos: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FiiAtivoPassivo:
    cnpj_fundo_classe: str
    data_referencia: str
    versao: str
    valores: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class FiiComplemento:
    cnpj_fundo_classe: str
    data_referencia: str
    versao: str
    valores: dict[str, float | None] = field(default_factory=dict)


def build_target(ano: int) -> CvmFiiTarget:
    """Build the request URL for a given year's FII monthly reports ZIP."""

    if ano < _FIRST_AVAILABLE_YEAR:
        raise ValueError(
            f"CVM's structured FII monthly report starts in {_FIRST_AVAILABLE_YEAR}"
        )
    url = f"{BASE_URL}/inf_mensal_fii_{ano}.zip"
    return CvmFiiTarget(ano=ano, url=url, year=ano)


def _parse_number(raw: str) -> float | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _read_csv_rows(archive: zipfile.ZipFile, filename_fragment: str) -> list[dict[str, str]]:
    matches = [name for name in archive.namelist() if filename_fragment in name]
    if not matches:
        return []
    with archive.open(matches[0]) as raw:
        text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
        reader = csv.DictReader(text, delimiter=";")
        return list(reader)


_GERAL_IDENTITY_FIELDS = {
    "cnpj_fundo_classe": "CNPJ_Fundo_Classe",
    "data_referencia": "Data_Referencia",
    "versao": "Versao",
    "tipo_fundo_classe": "Tipo_Fundo_Classe",
    "nome_fundo_classe": "Nome_Fundo_Classe",
    "segmento_atuacao": "Segmento_Atuacao",
    "tipo_gestao": "Tipo_Gestao",
    "mandato": "Mandato",
    "nome_administrador": "Nome_Administrador",
    "cnpj_administrador": "CNPJ_Administrador",
    "cidade": "Cidade",
    "estado": "Estado",
}


def parse_geral(body: bytes) -> tuple[FiiGeral, ...]:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = _read_csv_rows(archive, "_geral_")

    results = []
    for row in rows:
        known = {k: row.get(v) or None for k, v in _GERAL_IDENTITY_FIELDS.items()}
        others = {
            k: v for k, v in row.items() if k not in _GERAL_IDENTITY_FIELDS.values()
        }
        results.append(FiiGeral(**known, outros_campos=others))
    return tuple(results)


_IDENTITY_COLUMNS = {"CNPJ_Fundo_Classe", "Data_Referencia", "Versao"}


def parse_ativo_passivo(body: bytes) -> tuple[FiiAtivoPassivo, ...]:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = _read_csv_rows(archive, "_ativo_passivo_")

    results = []
    for row in rows:
        valores = {
            k: _parse_number(v) for k, v in row.items() if k not in _IDENTITY_COLUMNS
        }
        results.append(
            FiiAtivoPassivo(
                cnpj_fundo_classe=row.get("CNPJ_Fundo_Classe", ""),
                data_referencia=row.get("Data_Referencia", ""),
                versao=row.get("Versao", ""),
                valores=valores,
            )
        )
    return tuple(results)


def parse_complemento(body: bytes) -> tuple[FiiComplemento, ...]:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = _read_csv_rows(archive, "_complemento_")

    results = []
    for row in rows:
        valores = {
            k: _parse_number(v) for k, v in row.items() if k not in _IDENTITY_COLUMNS
        }
        results.append(
            FiiComplemento(
                cnpj_fundo_classe=row.get("CNPJ_Fundo_Classe", ""),
                data_referencia=row.get("Data_Referencia", ""),
                versao=row.get("Versao", ""),
                valores=valores,
            )
        )
    return tuple(results)
