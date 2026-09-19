"""CVM Fundos ICVM 555 (Renda Fixa e demais) — Informe Diário + Perfil Mensal.

Same rationale as ``cvm_fii``/``cvm_fiagro``: official CVM open data
(dados.cvm.gov.br), no login, no JS. Two genuinely different datasets,
structure verified directly against real downloaded files
(inf_diario_fi_202608.zip, perfil_mensal_fi_202608.csv), not assumed:

**Informe Diário** — dense daily NAV time series, one row per fund per
business day. Exactly the kind of historical series data emphasized
for the quantitative/timing analysis module: NAV (``VL_QUOTA``), net
asset value, daily inflows/outflows, shareholder count. History
available back to 2000 (a separate ``/HIST/`` path not covered by
this module's ``build_diario_target``, which targets the rolling
last-12-months monthly files: ``inf_diario_fi_{AAAAMM}.zip``). Only
10 columns, all named explicitly — no generic dict needed here, unlike
the other CVM sources.

**Perfil Mensal** — fund risk/shareholder-composition profile, one row
per fund per month. 107 columns; like FII's ativo_passivo and FIAGRO's
informe, only the identity columns are named explicitly
(``perfil_mensal_fi_{AAAAMM}.csv`` — plain CSV, NOT zipped, unlike
every other CVM dataset used so far in this project).

Files are ';'-delimited, Latin-1 (ISO-8859-1) encoded — same CVM
convention as the other sources.

Same request/response split as the other sources: this module builds
the request URL and parses the response; it performs no HTTP request
itself (see ``.cvm_renda_fixa_harvester`` for the transport).
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field

DIARIO_BASE_URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"
PERFIL_BASE_URL = "https://dados.cvm.gov.br/dados/FI/DOC/PERFIL_MENSAL/DADOS"


@dataclass(frozen=True)
class CvmDiarioTarget:
    ano: int
    mes: int
    url: str


@dataclass(frozen=True)
class CvmPerfilTarget:
    ano: int
    mes: int
    url: str


@dataclass(frozen=True)
class InformeDiario:
    tipo_fundo_classe: str | None
    cnpj_fundo_classe: str
    id_subclasse: str | None
    data_competencia: str
    valor_total: float | None
    valor_cota: float | None
    patrimonio_liquido: float | None
    captacao_dia: float | None
    resgate_dia: float | None
    numero_cotistas: int | None


@dataclass(frozen=True)
class PerfilMensal:
    tipo_fundo_classe: str | None
    cnpj_fundo_classe: str
    denominacao_social: str | None
    data_competencia: str
    versao: str
    valores: dict[str, str] = field(default_factory=dict)


def _competencia(ano: int, mes: int) -> str:
    if not (1 <= mes <= 12):
        raise ValueError(f"mes must be between 1 and 12, got {mes}")
    if ano < 2019:
        raise ValueError("Requested datasets start in 2019 (Perfil Mensal's floor)")
    return f"{ano:04d}{mes:02d}"


def build_diario_target(ano: int, mes: int) -> CvmDiarioTarget:
    """Build the request URL for a competência's daily-report ZIP."""
    competencia = _competencia(ano, mes)
    url = f"{DIARIO_BASE_URL}/inf_diario_fi_{competencia}.zip"
    return CvmDiarioTarget(ano=ano, mes=mes, url=url)


def build_perfil_target(ano: int, mes: int) -> CvmPerfilTarget:
    """Build the request URL for a competência's monthly profile CSV
    (plain CSV — not a ZIP, unlike every other CVM dataset used so
    far)."""
    competencia = _competencia(ano, mes)
    url = f"{PERFIL_BASE_URL}/perfil_mensal_fi_{competencia}.csv"
    return CvmPerfilTarget(ano=ano, mes=mes, url=url)


def _parse_float(raw: str) -> float | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(raw: str) -> int | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def parse_diario_response(body: bytes) -> tuple[InformeDiario, ...]:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        matches = [n for n in archive.namelist() if "inf_diario_fi_" in n]
        if not matches:
            return ()
        with archive.open(matches[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            reader = csv.DictReader(text, delimiter=";")
            rows = list(reader)

    results = []
    for row in rows:
        results.append(
            InformeDiario(
                tipo_fundo_classe=row.get("TP_FUNDO_CLASSE") or None,
                cnpj_fundo_classe=row.get("CNPJ_FUNDO_CLASSE", ""),
                id_subclasse=row.get("ID_SUBCLASSE") or None,
                data_competencia=row.get("DT_COMPTC", ""),
                valor_total=_parse_float(row.get("VL_TOTAL", "")),
                valor_cota=_parse_float(row.get("VL_QUOTA", "")),
                patrimonio_liquido=_parse_float(row.get("VL_PATRIM_LIQ", "")),
                captacao_dia=_parse_float(row.get("CAPTC_DIA", "")),
                resgate_dia=_parse_float(row.get("RESG_DIA", "")),
                numero_cotistas=_parse_int(row.get("NR_COTST", "")),
            )
        )
    return tuple(results)


_PERFIL_IDENTITY_COLUMNS = {
    "TP_FUNDO_CLASSE",
    "CNPJ_FUNDO_CLASSE",
    "DENOM_SOCIAL",
    "DT_COMPTC",
    "VERSAO",
}


def parse_perfil_response(body: bytes) -> tuple[PerfilMensal, ...]:
    text = io.StringIO(body.decode("latin-1"))
    reader = csv.DictReader(text, delimiter=";")

    results = []
    for row in reader:
        valores = {k: v for k, v in row.items() if k not in _PERFIL_IDENTITY_COLUMNS}
        results.append(
            PerfilMensal(
                tipo_fundo_classe=row.get("TP_FUNDO_CLASSE") or None,
                cnpj_fundo_classe=row.get("CNPJ_FUNDO_CLASSE", ""),
                denominacao_social=row.get("DENOM_SOCIAL") or None,
                data_competencia=row.get("DT_COMPTC", ""),
                versao=row.get("VERSAO", ""),
                valores=valores,
            )
        )
    return tuple(results)
