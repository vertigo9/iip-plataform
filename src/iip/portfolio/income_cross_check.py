"""Validação cruzada da renda projetada: a série da CVM contra o que a gestora declara.

Para cada FII da carteira compara a distribuição por cota projetada a partir da CVM
(``iip.portfolio.income``) com a que a gestora escreve no relatório mais recente
(``iip.sources.fii_distribution_reports``, ou a planilha de fundamentos da Pátria). Não
altera a renda projetada: registra se ela CONFERE, DIVERGE, ou se a CVM não tem número
confiável e só o gestor tem. A decisão de usar o número do gestor quando a CVM falha (o caso
do XPML11) é do usuário e não é tomada aqui.

Situações:
  - ``confere``: projeção da CVM e valor do gestor a até 5% um do outro;
  - ``mudanca_recente``: a projeção (mediana dos últimos meses) difere do gestor, mas o mês
    da CVM correspondente ao número do gestor CONFERE: o fundo mudou a distribuição há pouco e
    a mediana ainda não acompanha (conservadora se subiu, otimista se caiu);
  - ``diverge``: mais de 5% de diferença também no mês correspondente (o dado da CVM deste
    fundo não é confiável);
  - ``so_gestor``: a CVM não projeta (série irregular ou zerada) e o gestor declara um valor;
  - ``sem_gestor``: não há leitor do relatório deste fundo (ou não achou relatório);
  - ``leitura_falhou``: o relatório veio, mas o texto não casou com o layout, ou a busca falhou.

O resultado fica em ``02_Portfolio/Historical/_validacao.json``, ao lado das séries.
"""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from iip.portfolio.historical_series import HistoricalSeries, HistoricalSeriesStore
from iip.portfolio.income import DEFAULT_WINDOW, _per_unit, _project
from iip.portfolio.series_state import _probe
from iip.sources.fii_distribution_reports import DeclaredDistribution

VALIDATION_RELATIVE_PATH = Path("02_Portfolio") / "Historical" / "_validacao.json"

TOLERANCE = 0.05

STATUS_LABELS = {
    "confere": "confere",
    "mudanca_recente": "confere com o mês recente (a mediana está defasada)",
    "diverge": "diverge",
    "so_gestor": "só o gestor tem número",
    "sem_gestor": "sem fonte do gestor",
    "leitura_falhou": "leitura falhou",
}


@dataclass(frozen=True)
class CrossCheck:
    ticker: str
    status: str
    checked_at: str
    declared: float | None = None
    source_url: str | None = None
    evidence: str | None = None
    cvm_projection: float | None = None
    cvm_last: float | None = None
    cvm_last_period: str | None = None
    diff_projection: float | None = None  # (CVM - gestor) / gestor
    diff_last: float | None = None
    note: str = ""
    # a data do relatório / da distribuição do número do gestor, se a fonte a deixa ver
    reference: str | None = None

    @property
    def label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)


def _month_value(
    series: HistoricalSeries | None, period: str | None = None
) -> tuple[float | None, str | None]:
    """O valor por cota da CVM no mês ``period`` (AAAA-MM) ou, sem ele, no último mês com
    valor válido."""
    if series is None:
        return None, None
    valid = [
        o
        for o in sorted(series.observations, key=lambda o: o.period)
        if (_per_unit(o) or 0) > 0 and (period is None or o.period[:7] == period)
    ]
    if not valid:
        return None, None
    return round(_per_unit(valid[-1]), 6), valid[-1].period[:7]


def _diff(cvm: float | None, declared: float | None) -> float | None:
    if cvm is None or not declared:
        return None
    return (cvm - declared) / declared


def cross_check_fund(
    ticker: str,
    series: HistoricalSeries | None,
    declared: DeclaredDistribution | None,
    *,
    today: _dt.date,
    error: str | None = None,
    window: int = DEFAULT_WINDOW,
) -> CrossCheck:
    stamp = today.isoformat()
    projection = None
    if series is not None:
        line = _project(_probe(ticker), series, window)
        projection = line.per_unit if line.status == "projetada" else None
    cvm_last, cvm_last_period = _month_value(series)
    common = {
        "ticker": ticker,
        "checked_at": stamp,
        "cvm_projection": projection,
        "cvm_last": cvm_last,
        "cvm_last_period": cvm_last_period,
    }
    if error:
        return CrossCheck(**common, status="leitura_falhou", note=error)
    if declared is None:
        return CrossCheck(
            **common,
            status="sem_gestor",
            note="sem leitor do relatório deste fundo, ou nenhum relatório achado",
        )
    detail = {
        **common,
        "declared": declared.per_quota,
        "source_url": declared.source_url,
        "evidence": declared.evidence,
        "reference": declared.reference or declared.competencia,
        "diff_projection": _diff(projection, declared.per_quota),
        "diff_last": _diff(cvm_last, declared.per_quota),
    }
    if declared.competencia:
        # a fonte diz o mês: compara com o MESMO mês da CVM, não com o último
        same, same_period = _month_value(series, declared.competencia)
        detail["cvm_last"], detail["cvm_last_period"] = same, same_period
        detail["diff_last"] = _diff(same, declared.per_quota)
    if projection is None:
        return CrossCheck(
            **detail,
            status="so_gestor",
            note="a CVM não projeta este fundo (série irregular, zerada ou curta); o "
            "gestor declara um valor. Usá-lo no lugar da CVM é decisão do usuário",
        )
    if abs(detail["diff_projection"]) <= TOLERANCE:
        return CrossCheck(**detail, status="confere")
    if detail["diff_last"] is not None and abs(detail["diff_last"]) <= TOLERANCE:
        return CrossCheck(
            **detail,
            status="mudanca_recente",
            note="o mês da CVM correspondente confere com o gestor, mas a mediana dos "
            "últimos meses ficou para trás: a distribuição mudou há pouco",
        )
    return CrossCheck(**detail, status="diverge")


def run_cross_checks(
    tickers: tuple[str, ...],
    store: HistoricalSeriesStore,
    fetch_declared: Callable[[str], DeclaredDistribution | None],
    *,
    today: _dt.date,
) -> tuple[CrossCheck, ...]:
    results = []
    for ticker in tickers:
        try:
            series = store.load(ticker)
        except FileNotFoundError:
            series = None
        error = None
        declared = None
        try:
            declared = fetch_declared(ticker)
        # isolamento por fundo: a falha de um relatório não derruba a rodada
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        results.append(
            cross_check_fund(ticker, series, declared, today=today, error=error)
        )
    return tuple(results)


def save_validation(vault_path: str | Path, checks: tuple[CrossCheck, ...]) -> Path:
    path = Path(vault_path) / VALIDATION_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        c.ticker: {k: v for k, v in asdict(c).items() if k != "ticker"} for c in checks
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_validation(vault_path: str | Path) -> dict[str, CrossCheck]:
    path = Path(vault_path) / VALIDATION_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    out = {}
    for ticker, data in raw.items():
        try:
            out[ticker] = CrossCheck(ticker=ticker, **data)
        except TypeError:
            continue  # formato antigo: ignora em vez de quebrar a nota
    return out
