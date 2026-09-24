"""Novidade do monitoramento de pesos-alvo: o que mudou desde a última execução.

``monitoring_event.py`` descreve o estado atual de cada linha (uma leitura pura, sem memória).
Este módulo é a camada seguinte: compara essa leitura com o que já foi visto (persistido em
``02_Portfolio/estado_monitoramento.json``) e decide só uma coisa -- ``is_new``, se aquele
desvio é novidade ou já era conhecido. Nada aqui decide, executa, aporta ou rebalanceia; a regra
de negócio é só "isso já foi visto?", igual ao ``estado_alertas.json`` dos alertas macro, mas
sem janela nem confirmações (aqui é uma leitura de snapshot, não uma série temporal).

Reentrada é simples: uma linha que sai do desvio e o estado não guarda mais nada sobre ela; se
ela entrar em desvio de novo (mesmo tipo ou não), ``is_new`` volta a ``True``. Não há margem de
rearme como no macro -- sair do estado de desvio já é sair.

``alert_lines``/``write_alert_file`` só comunicam a novidade (uma linha de texto por desvio
NOVO); é o mesmo padrão de ``iip/macro/alerts.py``. Console/arquivo de alerta são lidos com
cp1252 no Windows: só ASCII simples nas mensagens (sem travessão nem seta).
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from iip.portfolio.monitoring_event import SEVERITY_DEVIATION, MonitoringEvent

STATE_RELATIVE_PATH = Path("02_Portfolio") / "estado_monitoramento.json"

CONTEXT_NOTICE = "Leitura informativa; nenhuma ordem foi gerada."


@dataclass(frozen=True)
class TrackedEvent:
    """Um ``MonitoringEvent`` mais a novidade: já era conhecido ou é a primeira vez que essa
    linha entra nesse ``deviation_type``. ``since`` só existe para linhas em desvio."""

    event: MonitoringEvent
    is_new: bool
    since: str | None


@dataclass(frozen=True)
class MonitoringRun:
    today: _dt.date
    policy_hash: str
    tracked: tuple[TrackedEvent, ...]
    state: dict = field(default_factory=dict)

    @property
    def deviations(self) -> tuple[TrackedEvent, ...]:
        return tuple(t for t in self.tracked if t.event.severity == SEVERITY_DEVIATION)

    @property
    def notifiable(self) -> tuple[TrackedEvent, ...]:
        return tuple(t for t in self.deviations if t.is_new)


def evaluate_run(
    events: tuple[MonitoringEvent, ...],
    previous_state: dict | None,
    today: _dt.date,
    policy_hash: str,
) -> MonitoringRun:
    """Compara ``events`` (a leitura de agora) com ``previous_state`` (o que já foi visto).

    Pura: não lê nem grava nada -- quem chama grava o estado devolvido (``MonitoringRun.state``).
    Reentrada simples: uma linha some do estado assim que sai do desvio; a próxima vez que
    entrar, é novidade de novo, mesmo que seja no mesmo ``deviation_type`` de antes.
    """
    previous_deviations = (previous_state or {}).get("deviations", {})
    today_text = today.isoformat()

    tracked: list[TrackedEvent] = []
    new_deviations: dict[str, dict] = {}
    for event in events:
        if event.severity != SEVERITY_DEVIATION:
            tracked.append(TrackedEvent(event, is_new=False, since=None))
            continue
        previous_entry = previous_deviations.get(event.line_id)
        if (
            previous_entry is None
            or previous_entry.get("deviation_type") != event.deviation_type
        ):
            is_new, since = True, today_text
        else:
            is_new, since = False, str(previous_entry.get("since", today_text))
        new_deviations[event.line_id] = {
            "deviation_type": event.deviation_type,
            "since": since,
        }
        tracked.append(TrackedEvent(event, is_new=is_new, since=since))

    state = {
        "type": "monitoring_state",
        "date": today_text,
        "policy_hash": policy_hash,
        "deviations": new_deviations,
    }
    return MonitoringRun(today, policy_hash, tuple(tracked), state)


# --- o estado (persistência) ----------------------------------------------------------------


def load_state(vault_path: str | Path) -> dict | None:
    """O estado gravado, ou ``None`` na primeira execução. Um estado ilegível levanta
    ``ValueError``: recomeçar do zero em silêncio reavisaria desvios já conhecidos."""
    path = Path(vault_path) / STATE_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path}: estado do monitoramento ilegível ({exc}); corrija ou apague o arquivo"
        ) from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("deviations", {}), dict):
        raise ValueError(
            f"{path}: estado do monitoramento mal formado; corrija ou apague o arquivo"
        )
    return raw


def save_state(vault_path: str | Path, state: dict) -> Path:
    path = Path(vault_path) / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# --- o arquivo de alerta ---------------------------------------------------------------------


def alert_lines(run: MonitoringRun) -> tuple[str, ...]:
    """Uma linha por desvio NOVO (``notifiable``); ASCII simples, sem travessão nem seta."""
    lines = []
    for tracked in run.notifiable:
        event = tracked.event
        lines.append(
            f"ATENCAO {event.line_id} entrou em desvio ({event.deviation_type}): peso atual "
            f"{event.current_weight_pct:.2f}% (faixa {event.band_low:.2f}-{event.band_high:.2f}%, "
            f"minimo {event.min_pct:.2f}%, maximo {event.max_pct:.2f}%). {CONTEXT_NOTICE}"
        )
    return tuple(lines)


def write_alert_file(path: Path | str, run: MonitoringRun) -> tuple[str, ...]:
    """Grava as linhas em ``path`` (UTF-8) ou, sem desvio novo, apaga o de uma rodada
    anterior. O arquivo é o que o agendador leria para a notificação do Windows (o job diário
    não chama este comando ainda -- é rodado manualmente)."""
    target = Path(path)
    lines = alert_lines(run)
    if lines:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        target.unlink(missing_ok=True)
    return lines
