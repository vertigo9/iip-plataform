"""Estado de cada série mensal da CVM e alertas de mudança.

A renda projetada depende das séries guardadas em ``02_Portfolio/Historical``. Uma série
pode falhar de cinco jeitos: sumir (ausente), parar de ser atualizada (defasada), trazer
rendimento zero ou negativo, ou ficar irregular demais para projetar (o mesmo critério de
``iip.portfolio.income``, reaproveitado aqui, não copiado). Este módulo guarda o estado de
cada uma e a data da última atualização, e avisa quando algo MUDA para pior.

O aviso é por mudança, não por condição: uma série que já estava irregular ontem não gera
o mesmo alerta toda semana (a nota ``Series.md`` continua mostrando o problema). Uma série
que volta ao normal não gera alerta.

O estado fica em ``02_Portfolio/Historical/_estado.json``, ao lado das séries:
``{ticker: {code, last_period, months, refreshed_at}}``.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from iip.portfolio.historical_series import HistoricalSeriesStore
from iip.portfolio.income import (
    DEFAULT_WINDOW,
    STALE_AFTER_MONTHS,
    _project,
)
from iip.universal.portfolio_state import PositionState

STATE_RELATIVE_PATH = Path("02_Portfolio") / "Historical" / "_estado.json"

# o que cada código de estado quer dizer, em português, para a nota e o alerta
CODE_LABELS = {
    "regular": "regular",
    "absent": "ausente",
    "zero": "rendimento zero ou negativo",
    "split": "desdobramento na janela",
    "few": "poucos meses",
    "irregular": "irregular",
}
# estados em que a série ainda serve para projetar renda
HEALTHY = frozenset({"regular"})


@dataclass(frozen=True)
class SeriesState:
    ticker: str
    code: str
    last_period: str | None
    months: int
    refreshed_at: str | None  # AAAA-MM-DD da última atualização bem-sucedida
    stale: bool

    @property
    def label(self) -> str:
        return CODE_LABELS.get(self.code, self.code)

    @classmethod
    def from_dict(cls, ticker: str, data: dict) -> SeriesState:
        return cls(
            ticker,
            data.get("code", "absent"),
            data.get("last_period"),
            int(data.get("months", 0)),
            data.get("refreshed_at"),
            bool(data.get("stale", False)),
        )


@dataclass(frozen=True)
class SeriesAlert:
    ticker: str
    kind: str  # "ausente", "defasada", "piorou"
    detail: str

    def line(self) -> str:
        return f"{self.ticker}: série {self.kind} — {self.detail}"


def _months_old(last_period: str, today: _dt.date) -> int:
    year, month = int(last_period[:4]), int(last_period[5:7])
    return (today.year - year) * 12 + (today.month - month)


def _probe(ticker: str) -> PositionState:
    # a classificação da série não depende da posição: quantidade e valor não entram
    return PositionState(ticker, 0.0, 0.0, 0.0, "fund")


def compute_state(
    ticker: str,
    store: HistoricalSeriesStore,
    *,
    today: _dt.date,
    refreshed_at: str | None,
    window: int = DEFAULT_WINDOW,
) -> SeriesState:
    try:
        series = store.load(ticker)
    except FileNotFoundError:
        return SeriesState(ticker, "absent", None, 0, refreshed_at, False)
    line = _project(_probe(ticker), series, window)
    last_period = line.last_period
    if last_period is None and series.observations:
        last_period = series.observations[-1].period[:7]
    months = sum(1 for o in series.observations if o.dividend_yield_mes is not None)
    stale = (
        last_period is not None and _months_old(last_period, today) > STALE_AFTER_MONTHS
    )
    return SeriesState(
        ticker, line.code or "absent", last_period, months, refreshed_at, stale
    )


def load_state_file(vault_path: str | Path) -> dict[str, dict]:
    path = Path(vault_path) / STATE_RELATIVE_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state_file(vault_path: str | Path, states: tuple[SeriesState, ...]) -> Path:
    path = Path(vault_path) / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        s.ticker: {k: v for k, v in asdict(s).items() if k != "ticker"} for s in states
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def series_alerts(
    previous: dict[str, dict], current: tuple[SeriesState, ...]
) -> tuple[SeriesAlert, ...]:
    """Só o que mudou para pior desde o estado anterior. Sem estado anterior (primeira
    execução) todo problema atual é novo."""
    alerts: list[SeriesAlert] = []
    for state in current:
        before = previous.get(state.ticker)
        before_code = before["code"] if before else None
        before_stale = bool(before and before.get("stale"))
        if state.code == "absent" and before_code != "absent":
            alerts.append(
                SeriesAlert(
                    state.ticker, "ausente", "não há série guardada para este FII"
                )
            )
            continue
        if state.stale and not before_stale:
            alerts.append(
                SeriesAlert(
                    state.ticker,
                    "defasada",
                    f"última competência {state.last_period}; a CVM já deveria ter "
                    "publicado meses mais novos",
                )
            )
        if (
            state.code not in HEALTHY
            and state.code != "absent"
            and before_code != state.code
        ):
            was = (
                f"era {CODE_LABELS.get(before_code, before_code)}"
                if before_code
                else "sem estado anterior"
            )
            alerts.append(
                SeriesAlert(state.ticker, "piorou", f"agora {state.label} ({was})")
            )
    return tuple(alerts)


def write_alert_file(
    path: Path | str, alerts: tuple[SeriesAlert, ...]
) -> tuple[SeriesAlert, ...]:
    """Uma linha por alerta; sem alerta, apaga o arquivo da rodada anterior."""
    target = Path(path)
    if alerts:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(a.line() for a in alerts) + "\n", encoding="utf-8")
    else:
        target.unlink(missing_ok=True)
    return alerts
