"""Universal asset pipeline for fund, equity, ETF, BDR and ADR signals."""

from __future__ import annotations

from dataclasses import dataclass

from .concentration import all_concentrations
from .cross_asset import CrossAssetSignal
from .portfolio_state import PortfolioState
from .taxonomy import AssetTaxonomy


@dataclass(frozen=True)
class UniversalPortfolioView:
    state: PortfolioState
    concentrations: tuple
    signals: tuple[CrossAssetSignal, ...]
    taxonomies: tuple[AssetTaxonomy, ...]


def build_view(
    state: PortfolioState,
    taxonomies: tuple[AssetTaxonomy, ...],
    signals: tuple[CrossAssetSignal, ...],
) -> UniversalPortfolioView:
    return UniversalPortfolioView(
        state=state,
        concentrations=all_concentrations(state.positions),
        signals=signals,
        taxonomies=taxonomies,
    )
