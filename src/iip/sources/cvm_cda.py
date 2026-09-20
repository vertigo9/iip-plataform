"""Composição da carteira (CDA) dos fundos, do dataset aberto da CVM.

Criado em 19/09/2026 para o FMP-FGTS Daycoval Eletrobras (registro AXIA3, CNPJ
45.121.022/0001-48), que não tem preço de mercado e por isso ficava sem valuation: a CDA
diz o que o fundo carrega, e isso permite avaliar por transparência (ver
``iip.portfolio_data.look_through``).

Fonte: ``https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_AAAAMM.zip`` (a versão
para máquinas do que a página "Composição da Carteira" do sistema SCW da CVM mostra).
Conferido ao vivo: publicado até agosto/2026 no dia 19/09/2026, ou seja, com ~3 semanas
de defasagem; 15 a 27 MB por mês. Dentro do zip:

  - ``cda_fi_PL_AAAAMM.csv``: uma linha por fundo com ``VL_PATRIM_LIQ`` na data da
    competência (``DT_COMPTC``, o último dia do mês);
  - ``cda_fi_BLC_4_AAAAMM.csv``: as ações em carteira (``CD_ATIVO``, ``TP_ATIVO``,
    ``CD_ISIN``, ``QT_POS_FINAL``, ``VL_MERC_POS_FINAL``). Os outros blocos (BLC_1 títulos
    públicos, BLC_8 disponibilidades e valores a pagar etc.) não são lidos: o peso de cada
    ação é ``VL_MERC_POS_FINAL`` sobre o patrimônio líquido, e o resto é o resto.

CSV em latin-1, separado por ``;``, decimais com ponto. O identificador do fundo é
``CNPJ_FUNDO_CLASSE`` (desde a CVM 175) ou ``CNPJ_FUNDO`` (antes). Para o FMP-FGTS, em
31/08/2026: patrimônio líquido R$ 129.177.461,25, com AXIA3 (ON) 1.952.953 ações
(R$ 103,74 mi) e AXIA7 (PN) 473.623 ações (R$ 25,17 mi), 99,8% do PL.

A composição é do fim do mês e o fundo mexe nela ao longo dele, então quem a usa a trata
como proporção aproximada, não como posição de hoje.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date

BASE_URL = "https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS"

_CNPJ_COLUMNS = ("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")


class CdaError(RuntimeError):
    """A CDA não pôde ser lida para o fundo pedido."""


@dataclass(frozen=True)
class CdaEquity:
    ticker: str
    isin: str | None
    kind: str | None  # "Ação ordinária", "Ação preferencial"...
    quantity: float
    market_value: float


@dataclass(frozen=True)
class CdaPortfolio:
    cnpj: str
    name: str
    month: str  # "AAAAMM"
    reference_date: str  # ISO, a data de competência
    net_assets: float
    equities: tuple[CdaEquity, ...]


def build_url(month: str) -> str:
    if not re.fullmatch(r"\d{6}", month):
        raise ValueError(f"month must be AAAAMM, got {month!r}")
    return f"{BASE_URL}/cda_fi_{month}.zip"


def recent_months(today: date, count: int = 3) -> tuple[str, ...]:
    """Do mês anterior para trás: o mês corrente ainda não foi publicado, e o anterior
    pode não ter sido ainda (a CVM leva algumas semanas)."""
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        months.append(f"{year:04d}{month:02d}")
    return tuple(months)


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _number(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw.strip())
    except ValueError:
        return None


def _rows(zf: zipfile.ZipFile, name: str, cnpj_digits: str):
    """As linhas do CSV ``name`` que são do fundo pedido (o arquivo tem todos os fundos)."""
    with zf.open(name) as raw:
        reader = csv.DictReader(
            io.TextIOWrapper(raw, encoding="latin-1"), delimiter=";"
        )
        column = next(
            (c for c in _CNPJ_COLUMNS if c in (reader.fieldnames or [])), None
        )
        if column is None:
            return
        for row in reader:
            if _digits(row.get(column, "")) == cnpj_digits:
                yield row


def parse_cda_zip(body: bytes, cnpj: str, month: str) -> CdaPortfolio | None:
    """A carteira do fundo nesse mês, ou ``None`` se o fundo não aparece (sem patrimônio
    líquido na CDA do mês). Uma ação com quantidade ou valor inválido é descartada; um
    zip sem o arquivo de patrimônio líquido dá ``CdaError``."""
    cnpj_digits = _digits(cnpj)
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile as exc:
        raise CdaError(f"arquivo da CDA de {month} não é um zip válido") from exc
    names = {n.lower(): n for n in zf.namelist()}
    pl_name = names.get(f"cda_fi_pl_{month}.csv")
    if pl_name is None:
        raise CdaError(f"a CDA de {month} não traz o arquivo de patrimônio líquido")
    pl_rows = list(_rows(zf, pl_name, cnpj_digits))
    if not pl_rows:
        return None
    pl_row = pl_rows[-1]
    net_assets = _number(pl_row.get("VL_PATRIM_LIQ"))
    if net_assets is None or net_assets <= 0:
        return None

    equities: list[CdaEquity] = []
    blc4 = names.get(f"cda_fi_blc_4_{month}.csv")
    if blc4 is not None:
        for row in _rows(zf, blc4, cnpj_digits):
            ticker = (row.get("CD_ATIVO") or "").strip().upper()
            quantity = _number(row.get("QT_POS_FINAL"))
            value = _number(row.get("VL_MERC_POS_FINAL"))
            if not ticker or quantity is None or value is None or value < 0:
                continue
            equities.append(
                CdaEquity(
                    ticker=ticker,
                    isin=(row.get("CD_ISIN") or "").strip() or None,
                    kind=(row.get("TP_ATIVO") or "").strip() or None,
                    quantity=quantity,
                    market_value=value,
                )
            )
    return CdaPortfolio(
        cnpj=cnpj,
        name=(pl_row.get("DENOM_SOCIAL") or "").strip(),
        month=month,
        reference_date=(pl_row.get("DT_COMPTC") or "").strip(),
        net_assets=net_assets,
        equities=tuple(equities),
    )
