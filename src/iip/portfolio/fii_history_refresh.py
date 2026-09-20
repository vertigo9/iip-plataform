"""Atualização das séries mensais da CVM (Informe Mensal de FII) guardadas no vault.

``collect_cvm_fii_history`` sabia montar a série, mas nenhum comando a chamava: a série de
cada FII em ``02_Portfolio/Historical/<TICKER>.json`` foi gravada uma vez (17/09/2026) e
nunca mais mudaria, e tudo que lê dela (a renda projetada, o painel de distribuições) ficaria
velho sem aviso. Aqui está o laço que a atualiza, com três cuidados:

  - a coleta refaz a série inteira dos anos pedidos, então ela só substitui a guardada se não
    trouxer MENOS meses (uma falha de rede no meio não pode apagar história);
  - um ajuste de desdobramento/grupamento já confirmado (``adjustments``) é reaplicado, porque
    a coleta crua devolve a cota patrimonial na escala antiga;
  - o isolamento é por posição: um fundo com erro não impede os outros.

O zip de cada ano cobre todos os fundos, e ``shared_fii_cache`` o baixa uma vez por rodada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from iip.portfolio.historical_series import (
    HistoricalSeries,
    HistoricalSeriesStore,
    collect_cvm_fii_history,
    normalize_quota_splits,
)
from iip.portfolio.registry import PortfolioAsset
from iip.sources.shared_caches import with_shared_fetch_caches


@dataclass(frozen=True)
class HistoryRefreshOutcome:
    ticker: str
    status: str  # "ok", "pulado" ou "erro"
    detail: str
    observations: int = 0
    added: int = 0
    last_period: str | None = None


class _CaptureStore(HistoricalSeriesStore):
    """Recebe a série da coleta sem gravá-la: quem decide se ela substitui a guardada é o
    laço de atualização."""

    def __init__(self, root: Any) -> None:
        super().__init__(root)
        self.captured: HistoricalSeries | None = None

    def save(self, series: HistoricalSeries):
        self.captured = series
        return self.path_for(series.ticker)


def fii_positions(positions: tuple[PortfolioAsset, ...]) -> tuple[PortfolioAsset, ...]:
    """Os FIIs com CNPJ conferido: os que o Informe Mensal de FII da CVM cobre."""
    return tuple(
        p
        for p in positions
        if p.asset_class == "fund" and p.subtype == "FII" and p.cnpj
    )


def _existing(store: HistoricalSeriesStore, ticker: str) -> HistoricalSeries | None:
    try:
        return store.load(ticker)
    except FileNotFoundError:
        return None


@with_shared_fetch_caches
def refresh_fii_histories(
    positions: tuple[PortfolioAsset, ...],
    *,
    store: HistoricalSeriesStore,
    years: range,
    harvester: Any = None,
    bridge: Any = None,
) -> tuple[HistoryRefreshOutcome, ...]:
    outcomes: list[HistoryRefreshOutcome] = []
    for position in positions:
        if not position.cnpj:
            outcomes.append(
                HistoryRefreshOutcome(position.ticker, "pulado", "sem CNPJ no registro")
            )
            continue
        previous = _existing(store, position.ticker)
        capture = _CaptureStore(store.root)
        try:
            collect_cvm_fii_history(
                position.ticker,
                position.cnpj,
                years,
                store=capture,
                harvester=harvester,
                bridge=bridge,
            )
            series = capture.captured
            if series is None or not series.observations:
                outcomes.append(
                    HistoryRefreshOutcome(
                        position.ticker,
                        "erro",
                        "a CVM não trouxe nenhum mês deste fundo nos anos pedidos",
                    )
                )
                continue
            before = len(previous.observations) if previous else 0
            if len(series.observations) < before:
                outcomes.append(
                    HistoryRefreshOutcome(
                        position.ticker,
                        "erro",
                        f"a coleta trouxe {len(series.observations)} meses e a série "
                        f"guardada tem {before}: série mantida (confira os anos pedidos)",
                        observations=before,
                    )
                )
                continue
            if previous is not None and previous.adjustments:
                series = normalize_quota_splits(series)
            store.save(series)
        # isolamento por posição, mesmo padrão dos lotes da carteira
        except Exception as exc:  # noqa: BLE001
            outcomes.append(HistoryRefreshOutcome(position.ticker, "erro", str(exc)))
            continue
        outcomes.append(
            HistoryRefreshOutcome(
                position.ticker,
                "ok",
                "série atualizada",
                observations=len(series.observations),
                added=len(series.observations) - before,
                last_period=series.observations[-1].period[:7],
            )
        )
    return tuple(outcomes)
