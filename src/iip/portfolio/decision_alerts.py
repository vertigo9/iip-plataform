"""Alerta de mudança de decisão: o que mudou entre a decisão anterior e a de hoje.

Só compara o veredito (a decisão de cada posição contra a mais recente gravada antes de
hoje); não há limiar nem regra de mercado aqui. O arquivo de alerta é o que o agendador
lê para mostrar a notificação do Windows: existe apenas quando houve mudança, e uma rodada
sem mudança apaga o de ontem, para nunca reavisar uma mudança velha.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from iip.portfolio.batch_decide import DecisionOutcome, DecisionRunResult

# do menos ao mais favorável (a mesma ordem de ``iip.decision.knowledge_bridge``, com o
# VENDER do motor no lugar do ENCERRAR do vault)
_ORDER = ("VENDER", "REDUZIR", "AGUARDAR", "MANTER", "COMPRAR", "AUMENTAR")


@dataclass(frozen=True)
class DecisionChange:
    ticker: str
    previous: str
    current: str
    direction: str  # "piora" ou "melhora"

    def line(self) -> str:
        return f"{self.ticker}: {self.previous} -> {self.current} ({self.direction})"


def _rank(verdict: str) -> int | None:
    return _ORDER.index(verdict) if verdict in _ORDER else None


def change_of(outcome: DecisionOutcome) -> DecisionChange | None:
    """A mudança da posição, ou ``None`` se não decidiu, é a primeira decisão ou não mudou.
    Um veredito fora da escala conhecida vira mudança sem direção inventada: "muda"."""
    if outcome.status != "ok" or not outcome.previous_verdict or not outcome.verdict:
        return None
    if outcome.previous_verdict == outcome.verdict:
        return None
    before, after = _rank(outcome.previous_verdict), _rank(outcome.verdict)
    direction = (
        "muda"
        if before is None or after is None
        else ("melhora" if after > before else "piora")
    )
    return DecisionChange(
        outcome.ticker, outcome.previous_verdict, outcome.verdict, direction
    )


def decision_changes(result: DecisionRunResult) -> tuple[DecisionChange, ...]:
    """As mudanças da rodada, as pioras primeiro (é o que pede atenção)."""
    changes = [c for o in result.outcomes if (c := change_of(o)) is not None]
    return tuple(sorted(changes, key=lambda c: (c.direction != "piora", c.ticker)))


def write_alert_file(
    path: Path | str, result: DecisionRunResult
) -> tuple[DecisionChange, ...]:
    """Grava uma linha por mudança em ``path`` (UTF-8) ou, sem mudança, apaga o arquivo
    que sobrou de uma rodada anterior. Devolve as mudanças."""
    target = Path(path)
    changes = decision_changes(result)
    if changes:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(c.line() for c in changes) + "\n", encoding="utf-8")
    else:
        target.unlink(missing_ok=True)
    return changes
