"""Vacância (e, daí, ocupação) lida do relatório gerencial da própria gestora.

Primeiro extrator de PDF de FII de tijolo fora da Pátria (item 6 do roadmap,
19/09/2026). Antes, ``occupancy_rate`` só vinha de dado real para HGRU11, LVBI11
e PVBI11 (planilha da Pátria); nos demais fundos de tijolo ficava no valor-padrão
do ``FIIAnalyzer``.

Cada gestora escreve a vacância de um jeito, e os cinco layouts abaixo foram
lidos ao vivo nos PDFs de 19/09/2026 (texto do ``pypdf``, sem OCR):

  - TRXF11 (Investor Report, em inglês): ``Vacancy Physical 0.67% and Financial
    0.42%`` -- as duas medidas, ponto decimal.
  - BTLG11 (Relatório Gerencial da BTG): caixa de destaques da página 2, com o
    rótulo ``VACÂNCIA FINANCEIRA`` seguido do valor (``1,2%``), no mesmo padrão
    dos vizinhos ``COTISTAS``/``VOLUME MENSAL``. Só a financeira.
  - HGBS11 (Relatório de Gestão da Hedge, shopping): ``VACÂNCIA: O Fundo
    encerrou jul/26 com 4,4% da ABL vaga`` -- só a FÍSICA (ABL), que é a medida
    padrão de shopping; o relatório não informa a financeira.

  - RBVA11 (Relatório Gerencial da Rio Bravo): caixa "PRINCIPAIS NÚMEROS" com o
    valor ANTES do rótulo (``8,3%`` e depois ``Vacância Física``) -- o inverso do
    BTLG11. Só a física.
  - KNRI11 (Carta do Gestor da Kinea, em prosa): ``a vacância física ao final do
    mês de agosto foi de 3,91% (ante 3,95% no mês anterior), a vacância financeira
    5,14% (...)``, com número de nota de rodapé colado à palavra (``física2``). O
    texto traz ainda a financeira "ajustada pelas carências", que NÃO é lida: é
    outra medida.

Base da medida. A Pátria usa ``1 - vacância financeira`` (ponderada por receita)
como ``occupancy_rate``. Aqui a financeira também vem primeiro; só quando o
relatório não a informa se usa a física, e a base fica registrada em
``VacanciaReading.basis`` para o chamador avisar -- nunca se troca uma pela
outra em silêncio.

Frágil por natureza (depende do texto de cada gestora): se o layout mudar, o
parser devolve ``None`` (dado ausente), nunca um número de outro contexto. Um
valor fora de 0-100% também é recusado.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class VacanciaReading:
    layout: str
    financial_vacancy_pct: float | None = None
    physical_vacancy_pct: float | None = None
    # mês de referência quando o próprio texto o traz (ex.: "jul/26"), senão None
    reference: str | None = None

    @property
    def basis(self) -> str | None:
        if self.financial_vacancy_pct is not None:
            return "financeira"
        if self.physical_vacancy_pct is not None:
            return "física"
        return None

    @property
    def occupancy_rate(self) -> float | None:
        """Fração 0-1 (a unidade do ``FIIAnalyzer``), como a da Pátria."""
        pct = (
            self.financial_vacancy_pct
            if self.financial_vacancy_pct is not None
            else self.physical_vacancy_pct
        )
        if pct is None:
            return None
        return round(1.0 - pct / 100.0, 6)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.lower().split())


def _pct(raw: str, *, decimal_comma: bool) -> float | None:
    try:
        value = float(raw.replace(",", ".") if decimal_comma else raw)
    except ValueError:
        return None
    return value if 0.0 <= value <= 100.0 else None


_TRX = re.compile(r"vacancy physical (\d+\.\d+)% and financial (\d+\.\d+)%")
_BTG = re.compile(r"vacancia financeira (\d+,\d+)%")
_HEDGE = re.compile(
    r"vacancia: o fundo encerrou ([a-z]{3}/\d{2}) com (\d+,\d+)% da abl vaga"
)


_RBVA = re.compile(r"(\d+,\d+)% vacancia fisica")
_KNRI = re.compile(
    r"vacancia fisica\d* ao final do mes de ([a-z]+) foi de (\d+,\d+)% "
    r"\(ante [^)]*\), a vacancia financeira\d* (\d+,\d+)%"
)


def parse_rbva(text: str) -> VacanciaReading | None:
    match = _RBVA.search(_normalize(text))
    if match is None:
        return None
    physical = _pct(match.group(1), decimal_comma=True)
    if physical is None:
        return None
    return VacanciaReading(
        "rio_bravo_relatorio_gerencial", physical_vacancy_pct=physical
    )


def parse_knri(text: str) -> VacanciaReading | None:
    match = _KNRI.search(_normalize(text))
    if match is None:
        return None
    physical = _pct(match.group(2), decimal_comma=True)
    financial = _pct(match.group(3), decimal_comma=True)
    if physical is None and financial is None:
        return None
    return VacanciaReading(
        "kinea_carta_do_gestor",
        financial_vacancy_pct=financial,
        physical_vacancy_pct=physical,
        reference=match.group(1),
    )


def parse_trx(text: str) -> VacanciaReading | None:
    match = _TRX.search(_normalize(text))
    if match is None:
        return None
    physical = _pct(match.group(1), decimal_comma=False)
    financial = _pct(match.group(2), decimal_comma=False)
    if physical is None and financial is None:
        return None
    return VacanciaReading(
        "trx_investor_report",
        financial_vacancy_pct=financial,
        physical_vacancy_pct=physical,
    )


def parse_btg(text: str) -> VacanciaReading | None:
    match = _BTG.search(_normalize(text))
    if match is None:
        return None
    financial = _pct(match.group(1), decimal_comma=True)
    if financial is None:
        return None
    return VacanciaReading("btg_relatorio_gerencial", financial_vacancy_pct=financial)


def parse_hedge(text: str) -> VacanciaReading | None:
    match = _HEDGE.search(_normalize(text))
    if match is None:
        return None
    physical = _pct(match.group(2), decimal_comma=True)
    if physical is None:
        return None
    return VacanciaReading(
        "hedge_relatorio_gestao",
        physical_vacancy_pct=physical,
        reference=match.group(1),
    )


@dataclass(frozen=True)
class VacanciaProfile:
    layout: str
    parser: Callable[[str], VacanciaReading | None]
    # páginas do PDF lidas: os destaques ficam no começo, e ler o documento
    # inteiro só aumenta a chance de casar um trecho de outro contexto
    max_pages: int


# Só entra aqui o ticker cujo layout foi lido ao vivo (ver docstring do módulo).
PROFILES: dict[str, VacanciaProfile] = {
    "TRXF11": VacanciaProfile("trx_investor_report", parse_trx, max_pages=6),
    "BTLG11": VacanciaProfile("btg_relatorio_gerencial", parse_btg, max_pages=6),
    "HGBS11": VacanciaProfile("hedge_relatorio_gestao", parse_hedge, max_pages=10),
    "RBVA11": VacanciaProfile("rio_bravo_relatorio_gerencial", parse_rbva, max_pages=6),
    "KNRI11": VacanciaProfile("kinea_carta_do_gestor", parse_knri, max_pages=6),
}


def profile_for_ticker(ticker: str) -> VacanciaProfile | None:
    return PROFILES.get(ticker.strip().upper())


_TRX_UPLOAD = re.compile(r"/uploads/(\d{4})/(\d{2})/[^/]*investor-report", re.I)
_HEDGE_FILE = re.compile(r"/(\d{4})_(\d{2})_HGBS_Relatorio\.pdf$", re.I)
_RBVA_FILE = re.compile(
    r"/RBVA11/relatorios/relatorios-(\d{4})-(\d{2})-(\d{2})-(\d+)\.pdf$"
)
_KNRI_CARTA = re.compile(r"/KNRI_Carta-do-Gestor_(\d{2})-(\d{4})\.pdf$", re.I)


def latest_trx_url(urls: Iterable[str]) -> str | None:
    """Investor Report mais recente: o nome do arquivo varia de mês a mês
    (``Investor-Report-06.2026``, ``TRXF11-Investor-Report-July-2026``,
    ``Investor-Report-April-2026``), então vale o ano/mês da PASTA de upload."""
    candidates = []
    for url in urls:
        match = _TRX_UPLOAD.search(url)
        if match:
            candidates.append(((int(match.group(1)), int(match.group(2))), url))
    return max(candidates)[1] if candidates else None


def latest_hedge_url(urls: Iterable[str]) -> str | None:
    """Relatório de Gestão mais recente do HGBS11 (``AAAA_MM_HGBS_Relatorio``)."""
    candidates = []
    for url in urls:
        match = _HEDGE_FILE.search(url)
        if match:
            candidates.append(((int(match.group(1)), int(match.group(2))), url))
    return max(candidates)[1] if candidates else None


def latest_rbva_url(urls: Iterable[str]) -> str | None:
    """Relatório gerencial mais recente do RBVA11 (``relatorios-AAAA-MM-DD-N``):
    vale a data e, na mesma data, o número maior (a republicação)."""
    candidates = []
    for url in urls:
        match = _RBVA_FILE.search(url)
        if match:
            year, month, day, serial = (int(g) for g in match.groups())
            candidates.append(((year, month, day, serial), url))
    return max(candidates)[1] if candidates else None


def latest_knri_url(urls: Iterable[str]) -> str | None:
    """Carta do Gestor mais recente do KNRI11 (``KNRI_Carta-do-Gestor_MM-AAAA``)."""
    candidates = []
    for url in urls:
        match = _KNRI_CARTA.search(url)
        if match:
            candidates.append(((int(match.group(2)), int(match.group(1))), url))
    return max(candidates)[1] if candidates else None
