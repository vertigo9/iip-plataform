"""Explicit end-to-end execution for one registered portfolio asset."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Callable

from iip.analysis import AssetData, FIIAnalyzer
from iip.knowledge import KnowledgeBridge
from iip.portfolio_data.valuation import ValuationMethod, ValuationSnapshot, build_snapshot
from iip.portfolio.historical_series import HistoricalSeriesStore
from iip.universal.concentration import all_concentrations
from iip.universal.portfolio_state import PortfolioState


@dataclass(frozen=True)
class E2EStep:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class AssetE2EResult:
    ticker: str
    template: dict[str, Any] | None
    analysis: Any | None
    valuation: ValuationSnapshot | None
    concentrations: tuple[Any, ...]
    quantitative: dict[str, float] | None
    steps: tuple[E2EStep, ...]

    @property
    def succeeded(self) -> bool:
        return all(step.status == "ok" for step in self.steps)


class AssetE2ERunner:
    """Run only verified product stages and report missing inputs explicitly."""

    def __init__(
        self,
        *,
        vault_path: str,
        bridge_factory: Callable[[str], KnowledgeBridge] = KnowledgeBridge,
        analyzer_factory: Callable[[], Any] = FIIAnalyzer,
    ) -> None:
        self.bridge = bridge_factory(vault_path)
        self.analyzer_factory = analyzer_factory

    def run(
        self,
        *,
        ticker: str,
        fetch_template: Callable[[], tuple[dict[str, Any], Any]],
        asset_class: str = "fii",
        fair_value: float | None = None,
        valuation_method: ValuationMethod = ValuationMethod.NAV,
        portfolio_state: PortfolioState | None = None,
        historical_series: tuple[float, ...] | None = None,
    ) -> AssetE2EResult:
        steps: list[E2EStep] = []
        template: dict[str, Any] | None = None
        analysis = None
        valuation = None
        concentrations: tuple[Any, ...] = ()
        quantitative: dict[str, float] | None = None

        try:
            template, fetch_result = fetch_template()
            warnings = getattr(fetch_result, "warnings", ())
            detail = "template collected"
            if warnings:
                detail += f"; warnings={'; '.join(warnings)}"
            steps.append(E2EStep("collection", "ok", detail))
        except Exception as exc:  # noqa: BLE001
            steps.append(E2EStep("collection", "error", f"{type(exc).__name__}: {exc}"))
            return AssetE2EResult(ticker, None, None, None, (), None, tuple(steps))

        try:
            data = AssetData(
                symbol=ticker,
                sector=template.get("sector", ""),
                industry=template.get("industry", ""),
                market_cap=template.get("market_cap"),
                price=template.get("price"),
                financials=template.get("financials", {}),
            )
            analysis = self.analyzer_factory().analyze(data)
            projection = self.bridge.sync_analysis_projection(analysis, ticker, asset_class)
            steps.append(E2EStep("fundamental_analysis", "ok", str(projection.path)))
        except Exception as exc:  # noqa: BLE001
            steps.append(E2EStep("fundamental_analysis", "error", f"{type(exc).__name__}: {exc}"))

        if fair_value is None:
            steps.append(E2EStep("valuation", "blocked", "fair_value is required; no valuation was fabricated"))
        else:
            valuation = build_snapshot(ticker, valuation_method, fair_value, template.get("price"))
            steps.append(E2EStep("valuation", "ok", f"margin_of_safety={valuation.margin_of_safety}"))

        if historical_series is None:
            steps.append(E2EStep("quantitative", "blocked", "historical_series is required"))
        else:
            if len(historical_series) < 2 or any(value <= 0 for value in historical_series):
                steps.append(E2EStep("quantitative", "blocked", "at least two positive observations are required"))
            else:
                returns = tuple(
                    (current / previous) - 1.0
                    for previous, current in zip(historical_series, historical_series[1:])
                )
                quantitative = {
                    "observations": float(len(historical_series)),
                    "mean_price": mean(historical_series),
                    "price_volatility": pstdev(historical_series),
                    "mean_return": mean(returns),
                    "return_volatility": pstdev(returns),
                    "total_return": (historical_series[-1] / historical_series[0]) - 1.0,
                }
                steps.append(E2EStep("quantitative", "ok", f"observations={len(historical_series)}; total_return={quantitative['total_return']:.6f}"))

        if portfolio_state is None:
            steps.append(E2EStep("cross_asset", "blocked", "portfolio_state is required"))
        else:
            concentrations = all_concentrations(portfolio_state.positions)
            steps.append(E2EStep("cross_asset", "ok", f"concentrations={len(concentrations)}"))

        return AssetE2EResult(ticker, template, analysis, valuation, concentrations, quantitative, tuple(steps))

    def run_with_persisted_series(
        self,
        *,
        ticker: str,
        fetch_template: Callable[[], tuple[dict[str, Any], Any]],
        series_store: HistoricalSeriesStore,
        asset_class: str = "fii",
        fair_value: float | None = None,
        valuation_method: ValuationMethod = ValuationMethod.NAV,
        portfolio_state: PortfolioState | None = None,
    ) -> AssetE2EResult:
        """Run the E2E flow using the persisted NAV history when valid."""
        series = series_store.load(ticker)
        if series.scale_breaks:
            result = self.run(
                ticker=ticker,
                fetch_template=fetch_template,
                asset_class=asset_class,
                fair_value=fair_value,
                valuation_method=valuation_method,
                portfolio_state=portfolio_state,
                historical_series=None,
            )
            steps = tuple(
                E2EStep(
                    "quantitative",
                    "blocked",
                    f"NAV scale break requires normalization: {series.scale_breaks}",
                )
                if step.name == "quantitative"
                else step
                for step in result.steps
            )
            return AssetE2EResult(
                result.ticker,
                result.template,
                result.analysis,
                result.valuation,
                result.concentrations,
                result.quantitative,
                steps,
            )
        return self.run(
            ticker=ticker,
            fetch_template=fetch_template,
            asset_class=asset_class,
            fair_value=fair_value,
            valuation_method=valuation_method,
            portfolio_state=portfolio_state,
            historical_series=series.nav_values,
        )
