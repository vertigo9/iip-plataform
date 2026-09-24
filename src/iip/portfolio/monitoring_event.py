"""Camada de leitura estruturada do monitoramento de pesos-alvo.

Traduz a leitura pura que já existe em ``target_policy.py`` (``reconcile`` + ``read_weight``)
num evento por linha, sem decidir nem executar nada: o monitor responde "o que mudou?", nunca
"o que fazer?". Decisões de investimento (REDUZIR, VENDER, MANTER, aporte, rebalanceamento)
pertencem à camada de valuation/decisão (``decide-portfolio``), que este módulo não conhece,
não importa e não chama.

Este módulo é só a camada de dados: ``build_monitoring_events`` não tem I/O, não lê o relógio e
não persiste nada. É consumido pelo comando manual ``iip monitoring-events`` e, desde o job
diário (``executar_atualizacao_diaria.ps1``, passo "Monitoramento de pesos-alvo"), também pela
execução automática das 08:00 -- em nenhum dos dois casos o módulo decide, executa ou aponta
para onde o evento vai; quem faz isso é ``monitoring_state.py`` (novidade) e, na ponta,
``decide-portfolio``/``rebalancing_alerts``, que este módulo continua sem conhecer, importar
ou chamar. O contrato também não decide para onde o evento seria encaminhado: isso fica fora do
dado até essa integração ser desenhada.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from iip.portfolio.target_policy import (
    PolicyLine,
    Reconciliation,
    TargetPolicy,
    read_weight,
)

# campo travado: este módulo nunca decide nem executa, e o dado deixa isso explícito
AUTOMATIC_ACTION = "nenhuma"

SEVERITY_INFO = "informativo"
SEVERITY_DEVIATION = "desvio"


@dataclass(frozen=True)
class MonitoringEvent:
    """Leitura estruturada de uma linha da política contra o peso atual no snapshot.

    Puramente descritiva. ``automatic_action`` é sempre ``AUTOMATIC_ACTION`` ("nenhuma"): o
    campo existe para deixar explícito, no próprio dado (não só na documentação), que este
    evento nunca decide nem executa nada.
    """

    line_id: str
    line_name: str
    asset_class: str
    current_weight_pct: float
    target_pct: float | None
    tolerance_pp: float | None
    min_pct: float | None
    max_pct: float | None
    band_low: float | None
    band_high: float | None
    stage: str
    state: str
    severity: str
    deviation_type: str | None
    automatic_action: str
    generated_at: str
    policy_hash: str


def _deviation_type(state: str, label: str) -> str | None:
    """Deriva o tipo de desvio a partir do ``state``/``label`` já calculados por
    ``read_weight``; não recalcula limites, só interpreta o resultado dela."""
    if state == "acima_do_maximo":
        return "acima_do_maximo"
    if state == "abaixo_do_minimo":
        return "abaixo_do_minimo"
    if state == "fora_da_faixa":
        return "acima_da_faixa" if "acima" in label else "abaixo_da_faixa"
    return None


def _band(line: PolicyLine) -> tuple[float | None, float | None]:
    if line.target_pct is None or line.tolerance_pp is None:
        return None, None
    return line.target_pct - line.tolerance_pp, line.target_pct + line.tolerance_pp


def _event_for_line(
    line: PolicyLine, weight_pct: float, *, generated_at: str, policy_hash: str
) -> MonitoringEvent:
    reading = read_weight(line, weight_pct)
    band_low, band_high = _band(line)
    return MonitoringEvent(
        line_id=line.id,
        line_name=line.name,
        asset_class=line.asset_class,
        current_weight_pct=weight_pct,
        target_pct=line.target_pct,
        tolerance_pp=line.tolerance_pp,
        min_pct=line.min_pct,
        max_pct=line.max_pct,
        band_low=band_low,
        band_high=band_high,
        stage=line.stage,
        state=reading.state,
        severity=SEVERITY_DEVIATION if reading.is_deviation else SEVERITY_INFO,
        deviation_type=_deviation_type(reading.state, reading.label),
        automatic_action=AUTOMATIC_ACTION,
        generated_at=generated_at,
        policy_hash=policy_hash,
    )


def build_monitoring_events(
    policy: TargetPolicy, rec: Reconciliation, generated_at: _dt.datetime | str
) -> tuple[MonitoringEvent, ...]:
    """Um ``MonitoringEvent`` por linha de ``rec.weights`` (todas, não só as em desvio).

    Puramente descritiva: não decide, não executa, não persiste, não chama nada de fora.
    ``generated_at`` é sempre recebido de quem chama (nunca lido do relógio aqui), para a
    função ficar determinística e sem efeito colateral, como ``render_policy_report``.
    """
    timestamp = (
        generated_at.isoformat()
        if isinstance(generated_at, _dt.datetime)
        else generated_at
    )
    policy_hash = policy.content_hash
    return tuple(
        _event_for_line(
            item.line, item.weight_pct, generated_at=timestamp, policy_hash=policy_hash
        )
        for item in rec.weights
    )
