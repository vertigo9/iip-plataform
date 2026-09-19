"""Vacância (e, daí, ocupação) lida do relatório gerencial da própria gestora.

Primeiro extrator de PDF de FII de tijolo fora da Pátria (item 6 do roadmap,
19/09/2026). Antes, ``occupancy_rate`` só vinha de dado real para HGRU11, LVBI11
e PVBI11 (planilha da Pátria); nos demais fundos de tijolo ficava no valor-padrão
do ``FIIAnalyzer``.

Cada gestora escreve a vacância de um jeito, e os oito layouts abaixo foram
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
  - HSML11 (Relatório Gerencial da HSI, shopping): a taxa de ocupação do FUNDO vem
    num gráfico de barras: uma linha com 12 percentuais (``96,6% ... 96,4%``), a
    linha dos 12 meses (``ago-25 ... jul-26``) e o título ``Taxa de Ocupação (%)``,
    com a nota "ponderada pela participação do Fundo nos shoppings". Vale o último
    par (aqui 96,4% em jul-26), e só se a quantidade de percentuais for igual à de
    meses. O relatório não diz a base; para shopping a taxa de ocupação é a da
    ABL, então entra como vacância FÍSICA (100 - taxa) e o aviso de base física
    aparece. ``Custo de Ocupação`` é outro gráfico e não é lido.
  - XPML11 (Relatório Gerencial da XP Asset, shopping): tabela "Indicadores
    Operacionais e Financeiros" com colunas ``Jul-26 | Ano (2026) | 12 meses`` e a
    linha ``Vacância (% ABL) média 4,7% 4,0% 3,9%``; vale a coluna do mês (a
    primeira), o mesmo número do texto corrido ("a vacância ... encerrou o período em
    4,7%"). O glossário do relatório define vacância como "ABL próprio total vago
    dividido pela ABL próprio total": é FÍSICA, com a base declarada.
  - ALZR11 (Relatório Gerencial da Alianza, contratos atípicos): NÃO traz nenhum total
    do fundo, só ``Ocupação do Imóvel`` em cada um dos 26 blocos do anexo (cada bloco
    tem ``Participação no Imóvel``, ``Área Bruta Locável`` -- ou ``Área BOMA`` -- e a
    ocupação). Aqui o número é CALCULADO por nós, não lido: média da ocupação por ABL
    própria (ABL x participação do fundo), a ocupação física por definição (a mesma do
    glossário da XP). Portões: a quantidade de blocos tem de bater com o ``Número de
    Ativos`` do resumo (26) e todo bloco tem de ser lido por completo, senão nada. A
    soma das ABL do anexo (265 mil m2) NÃO fecha com o ``ABL Total`` declarado (288,7
    mil m2, que "considera" ativos da 8ª emissão) -- a diferença vai no ``note`` da
    leitura, e o chamador a mostra. O valor de agosto/2026 é 99,8%: só o Pueri Domus
    (97%) não está cheio.

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

import html as _html
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass(frozen=True)
class VacanciaReading:
    layout: str
    financial_vacancy_pct: float | None = None
    physical_vacancy_pct: float | None = None
    # mês de referência quando o próprio texto o traz (ex.: "jul/26"), senão None
    reference: str | None = None
    # quando o número é CALCULADO em vez de lido (ver o ALZR11), o que foi feito e o que
    # não pôde ser conferido; o chamador mostra isso como aviso
    note: str | None = None

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


_HSI = re.compile(r"((?:\d+,\d+% ){6,})((?:[a-z]{3}-\d{2} ){6,})taxa de ocupacao \(%\)")


def parse_hsi(text: str) -> VacanciaReading | None:
    match = _HSI.search(_normalize(text))
    if match is None:
        return None
    rates = re.findall(r"(\d+,\d+)%", match.group(1))
    months = re.findall(r"([a-z]{3}-\d{2})", match.group(2))
    if len(rates) != len(months):
        # o gráfico não casou (uma barra sem rótulo ou o contrário): melhor nada
        return None
    occupancy = _pct(rates[-1], decimal_comma=True)
    if occupancy is None:
        return None
    return VacanciaReading(
        "hsi_relatorio_gerencial",
        physical_vacancy_pct=round(100.0 - occupancy, 4),
        reference=months[-1],
    )


_XP_HEADER = re.compile(r"operacionais ([a-z]{3}-\d{2}) ano \(\d{4}\) 12 meses")
_XP_ROW = re.compile(r"vacancia \(% abl\) media (\d+,\d+)% \d+,\d+% \d+,\d+%")


def parse_xp(text: str) -> VacanciaReading | None:
    normalized = _normalize(text)
    header = _XP_HEADER.search(normalized)
    row = _XP_ROW.search(normalized)
    # a coluna do mês só é a primeira se o cabeçalho a rotula assim, e a linha tem de
    # vir depois dele; sem os dois, melhor nada
    if header is None or row is None or row.start() < header.start():
        return None
    physical = _pct(row.group(1), decimal_comma=True)
    if physical is None:
        return None
    return VacanciaReading(
        "xp_relatorio_gerencial",
        physical_vacancy_pct=physical,
        reference=header.group(1),
    )


_ALZR_ASSETS = re.compile(r"numero de ativos\d? (\d+)")
_ALZR_ABL_TOTAL = re.compile(r"abl total\d? ([\d.]+) ?m2")
_ALZR_PARTICIPATION = re.compile(r"participacao no imovel (\d+(?:,\d+)?)%")
_ALZR_AREA = re.compile(r"area (?:bruta locavel|boma) ([\d.]+) ?m2")
_ALZR_OCCUPANCY = re.compile(r"ocupacao do imovel (\d+(?:,\d+)?)%")


def _br_number(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _pt_int(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def parse_alzr(text: str) -> VacanciaReading | None:
    normalized = _normalize(text)
    declared_assets = _ALZR_ASSETS.search(normalized)
    if declared_assets is None:
        return None
    starts = [m.start() for m in re.finditer("classe do imovel", normalized)]
    blocks = [normalized[a:b] for a, b in zip(starts, [*starts[1:], len(normalized)])]
    blocks = [b for b in blocks if "ocupacao do imovel" in b]
    if len(blocks) != int(declared_assets.group(1)):
        # o anexo não tem todos os imóveis (ou o layout mudou): melhor nada
        return None

    total_abl = own_abl = leased_abl = 0.0
    for block in blocks:
        participation = _ALZR_PARTICIPATION.search(block)
        area = _ALZR_AREA.search(block)
        occupancy = _ALZR_OCCUPANCY.search(block)
        if not (participation and area and occupancy):
            return None
        share = _pct(participation.group(1), decimal_comma=True)
        occ = _pct(occupancy.group(1), decimal_comma=True)
        abl = _br_number(area.group(1))
        if share is None or occ is None:
            return None
        total_abl += abl
        own_abl += abl * share / 100.0
        leased_abl += abl * share / 100.0 * occ / 100.0
    if own_abl <= 0:
        return None

    occupancy_pct = leased_abl / own_abl * 100.0
    declared_abl = _ALZR_ABL_TOTAL.search(normalized)
    reconciliation = "o relatório não traz o ABL Total para conferir"
    if declared_abl is not None:
        declared = _br_number(declared_abl.group(1))
        gap = (declared - total_abl) / declared * 100.0
        if abs(gap) < 0.5:
            reconciliation = "a soma das ABL confere com o ABL Total declarado"
        else:
            reconciliation = (
                f"a soma das ABL do anexo ({_pt_int(total_abl)} m2) fica {gap:.1f}% "
                f"abaixo do ABL Total declarado ({_pt_int(declared)} m2), que considera "
                "ativos da 8ª emissão: não foi possível conferir o restante"
            )
    return VacanciaReading(
        "alianza_relatorio_gerencial",
        physical_vacancy_pct=round(100.0 - occupancy_pct, 4),
        note=(
            "ocupação CALCULADA pelo IIP, não lida do relatório (que só informa a "
            f"ocupação de cada imóvel): média por ABL própria dos {len(blocks)} imóveis "
            f"do anexo; {reconciliation}."
        ),
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
    "HSML11": VacanciaProfile("hsi_relatorio_gerencial", parse_hsi, max_pages=15),
    "XPML11": VacanciaProfile("xp_relatorio_gerencial", parse_xp, max_pages=21),
    "ALZR11": VacanciaProfile("alianza_relatorio_gerencial", parse_alzr, max_pages=40),
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


_ALIANZA_LINK = re.compile(
    r"""<a\b[^>]*\bhref=["']([^"']*Download\.aspx[^"']*)["'][^>]*>(.*?)</a>""",
    re.I | re.S,
)
_ALIANZA_TITLE = re.compile(r"(\d{2})/(\d{2})/(\d{4}) - relatorio gerencial")


def latest_alianza_url(page_html: str, base_url: str) -> str | None:
    """Relatório gerencial mais recente na home do ALZR11: um link ``Download.aspx``
    cujo texto é ``18/09/2026 - Relatório Gerencial - Ago/26`` (vale a data do texto).
    """
    candidates = []
    for href, label in _ALIANZA_LINK.findall(page_html):
        text = _normalize(_html.unescape(re.sub(r"<[^>]+>", " ", label)))
        match = _ALIANZA_TITLE.search(text)
        if match:
            day, month, year = (int(g) for g in match.groups())
            url = urljoin(base_url, _html.unescape(href))
            candidates.append(((year, month, day), url))
    return max(candidates)[1] if candidates else None
