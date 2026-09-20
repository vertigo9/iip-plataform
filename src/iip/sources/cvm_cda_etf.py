"""Carteira de um ETF de renda fixa, da CDA do dataset aberto da CVM.

Criado em 20/09/2026 para o LFTB11 (CNPJ 56.176.507/0001-55). Ele não aparece nos
arquivos ``cda_fi_PL`` / ``cda_fi_BLC_*`` que ``iip.sources.cvm_cda`` lê (consta como
"CLASSES FIIM"): a carteira dele vem em ``cda_fie_AAAAMM.csv``, dentro do mesmo zip, com uma
linha por posição e o patrimônio líquido repetido em ``VL_PATRIM_LIQ``. Conferido ao vivo
(CDA de 08/2026, competência 31/08/2026, 25 linhas): PL R$ 5.419,6 mi e 17 títulos
públicos que somam 99,99% dele, o resto sendo cotas de fundos de R$ 1,6 mi e linhas de
despesas a pagar e a receber.

Isto substitui, para este fim, o que a página da gestora oferece: a "composição" da página
(HTML) não tem data e cobre 12 dos 17 ativos, e a cesta de integralização (XLSX) traz
quantidades por lote de criação, não pesos. A CDA traz o dia de referência, todos os
títulos, valor de mercado e vencimento.

A CDA não rotula o tipo do título (``TP_ATIVO`` e ``CD_ATIVO`` vêm vazios): só o vencimento
e o valor. Aqui nada é inferido a partir do vencimento; quem lê vê a data. Como em
``cvm_cda``, a composição é do fim do mês e serve como proporção aproximada, com ~3
semanas de defasagem.
"""

from __future__ import annotations

import csv
import io
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date

from .cvm_cda import CdaError, _digits, _number

_CNPJ_COLUMNS = ("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")


@dataclass(frozen=True)
class CdaBond:
    maturity: date
    quantity: float
    market_value: float


@dataclass(frozen=True)
class CdaEtfPortfolio:
    cnpj: str
    name: str
    month: str  # "AAAAMM"
    reference_date: date
    net_assets: float
    bonds: tuple[CdaBond, ...]


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(c for c in stripped if not unicodedata.combining(c)).strip().lower()


def _date(raw: str | None) -> date | None:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def parse_cda_etf_zip(body: bytes, cnpj: str, month: str) -> CdaEtfPortfolio | None:
    """A carteira do ETF nesse mês, ou ``None`` se ele não aparece no arquivo. Um título
    sem vencimento, quantidade ou valor válidos é descartado (e por isso a soma pode ficar
    abaixo do patrimônio: ``bonds_coverage`` diz quanto). Um zip sem o arquivo dos fundos
    de índice dá ``CdaError``."""
    cnpj_digits = _digits(cnpj)
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile as exc:
        raise CdaError(f"arquivo da CDA de {month} não é um zip válido") from exc
    names = {n.lower(): n for n in zf.namelist()}
    name = names.get(f"cda_fie_{month}.csv")
    if name is None:
        raise CdaError(
            f"a CDA de {month} não traz o arquivo cda_fie de fundos de índice"
        )

    with zf.open(name) as raw:
        reader = csv.DictReader(
            io.TextIOWrapper(raw, encoding="latin-1"), delimiter=";"
        )
        column = next(
            (c for c in _CNPJ_COLUMNS if c in (reader.fieldnames or [])), None
        )
        if column is None:
            raise CdaError(f"o cda_fie de {month} não tem coluna de CNPJ")
        rows = [r for r in reader if _digits(r.get(column, "")) == cnpj_digits]
    if not rows:
        return None

    net_assets = _number(rows[-1].get("VL_PATRIM_LIQ"))
    reference = _date(rows[-1].get("DT_COMPTC"))
    if net_assets is None or net_assets <= 0 or reference is None:
        return None

    bonds: list[CdaBond] = []
    for row in rows:
        if not _normalize(row.get("TP_APLIC") or "").startswith("titulos publicos"):
            continue
        maturity = _date(row.get("DT_VENC"))
        quantity = _number(row.get("QT_POS_FINAL"))
        value = _number(row.get("VL_MERC_POS_FINAL"))
        if maturity is None or quantity is None or value is None or value <= 0:
            continue
        bonds.append(CdaBond(maturity, quantity, value))
    return CdaEtfPortfolio(
        cnpj=cnpj,
        name=(rows[-1].get("DENOM_SOCIAL") or "").strip(),
        month=month,
        reference_date=reference,
        net_assets=net_assets,
        bonds=tuple(sorted(bonds, key=lambda b: b.maturity)),
    )


def bonds_coverage(portfolio: CdaEtfPortfolio) -> float:
    """Fração do patrimônio líquido em títulos públicos com dados válidos."""
    return sum(b.market_value for b in portfolio.bonds) / portfolio.net_assets


def bond_weights(portfolio: CdaEtfPortfolio) -> tuple[tuple[date, float], ...]:
    """(vencimento, peso sobre o patrimônio líquido), do vencimento mais próximo ao mais
    distante. Vencimentos iguais somam."""
    by_maturity: dict[date, float] = {}
    for bond in portfolio.bonds:
        by_maturity[bond.maturity] = (
            by_maturity.get(bond.maturity, 0.0) + bond.market_value
        )
    return tuple(
        (maturity, value / portfolio.net_assets)
        for maturity, value in sorted(by_maturity.items())
    )


def weighted_average_maturity_years(portfolio: CdaEtfPortfolio) -> float | None:
    """Prazo médio até o vencimento, ponderado pelo valor de mercado e medido a partir da
    data da CDA. NÃO é duration: em título pós-fixado o prazo até o vencimento diz pouco do
    risco de juros. ``None`` sem título."""
    total = sum(b.market_value for b in portfolio.bonds)
    if total <= 0:
        return None
    reference = portfolio.reference_date
    return (
        sum(
            b.market_value * (b.maturity - reference).days / 365.25
            for b in portfolio.bonds
        )
        / total
    )


def share_maturing_after_years(portfolio: CdaEtfPortfolio, years: float) -> float:
    """Fração do patrimônio líquido em títulos que vencem mais de ``years`` anos depois da
    data da CDA."""
    reference = portfolio.reference_date
    return (
        sum(
            b.market_value
            for b in portfolio.bonds
            if (b.maturity - reference).days / 365.25 > years
        )
        / portfolio.net_assets
    )
