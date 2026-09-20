"""Explicit end-to-end execution for one registered portfolio asset."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Callable

from iip.analysis import AssetData, FIIAnalyzer
from iip.knowledge import KnowledgeBridge
from iip.portfolio.historical_series import HistoricalSeriesStore
from iip.portfolio_data.valuation import (
    ValuationMethod,
    ValuationSnapshot,
    build_snapshot,
)
from iip.portfolio_data.valuation_exceptions import exceptions_for
from iip.portfolio_data.valuation_methods import evaluate_valuations, first_valuation
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
        # as exceções metodológicas do vault valem também aqui (arquivo inválido levanta)
        self._exceptions = exceptions_for(vault_path)

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
        market_inputs: Mapping[str, float | None] | None = None,
    ) -> AssetE2EResult:
        """``market_inputs``: market-wide numbers the valuation catalog may need
        that are not properties of the asset (e.g. ``ntnb_real_yield`` for
        Bazin). Supplied by the caller; this runner does no network I/O for it."""
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
            projection = self.bridge.sync_analysis_projection(
                analysis, ticker, asset_class
            )
            steps.append(E2EStep("fundamental_analysis", "ok", str(projection.path)))
        except Exception as exc:  # noqa: BLE001
            steps.append(
                E2EStep("fundamental_analysis", "error", f"{type(exc).__name__}: {exc}")
            )

        if fair_value is None:
            # No caller-supplied fair value: let the catalog pick the methods
            # that fit this asset (class + sector) and compute what it can from
            # the template. Nothing is invented -- if no method yields a value
            # the stage stays blocked, now listing why each one did not.
            attempts = evaluate_valuations(
                ticker=ticker,
                asset_class=asset_class,
                sector=template.get("sector") or "",
                industry=template.get("industry") or "",
                price=template.get("price"),
                inputs={**template.get("financials", {}), **(market_inputs or {})},
                exceptions=self._exceptions,
            )
            valuation = first_valuation(attempts)
            if valuation is None:
                why = "; ".join(
                    f"{a.method.value}={a.status} ({a.reason})" for a in attempts
                )
                steps.append(
                    E2EStep(
                        "valuation",
                        "blocked",
                        f"fair_value is required; no valuation was fabricated. Methods tried: {why}",
                    )
                )
            else:
                try:
                    self.bridge.sync_valuation_projection(
                        valuation, ticker, asset_class
                    )
                    steps.append(
                        E2EStep(
                            "valuation",
                            "ok",
                            f"{valuation.method.value}: margin_of_safety={valuation.margin_of_safety}",
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    steps.append(
                        E2EStep("valuation", "error", f"{type(exc).__name__}: {exc}")
                    )
        else:
            try:
                valuation = build_snapshot(
                    ticker, valuation_method, fair_value, template.get("price")
                )
                self.bridge.sync_valuation_projection(valuation, ticker, asset_class)
                steps.append(
                    E2EStep(
                        "valuation",
                        "ok",
                        f"margin_of_safety={valuation.margin_of_safety}",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                steps.append(
                    E2EStep("valuation", "error", f"{type(exc).__name__}: {exc}")
                )

        if historical_series is None:
            steps.append(
                E2EStep("quantitative", "blocked", "historical_series is required")
            )
        else:
            if len(historical_series) < 2 or any(
                value <= 0 for value in historical_series
            ):
                steps.append(
                    E2EStep(
                        "quantitative",
                        "blocked",
                        "at least two positive observations are required",
                    )
                )
            else:
                try:
                    returns = tuple(
                        (current / previous) - 1.0
                        for previous, current in zip(
                            historical_series, historical_series[1:]
                        )
                    )
                    quantitative = {
                        "observations": float(len(historical_series)),
                        "mean_price": mean(historical_series),
                        "price_volatility": pstdev(historical_series),
                        "mean_return": mean(returns),
                        "return_volatility": pstdev(returns),
                        "total_return": (historical_series[-1] / historical_series[0])
                        - 1.0,
                    }
                    self.bridge.sync_quantitative_projection(
                        quantitative, ticker, asset_class
                    )
                    steps.append(
                        E2EStep(
                            "quantitative",
                            "ok",
                            f"observations={len(historical_series)}; total_return={quantitative['total_return']:.6f}",
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    steps.append(
                        E2EStep("quantitative", "error", f"{type(exc).__name__}: {exc}")
                    )

        if portfolio_state is None:
            steps.append(
                E2EStep("cross_asset", "blocked", "portfolio_state is required")
            )
        else:
            try:
                concentrations = all_concentrations(portfolio_state.positions)
                own_position = next(
                    (p for p in portfolio_state.positions if p.ticker == ticker), None
                )
                own_dimensions = tuple(
                    value
                    for value in (
                        getattr(own_position, "manager", None),
                        getattr(own_position, "segment", None),
                        getattr(own_position, "asset_class", None),
                    )
                    if value
                )
                self.bridge.sync_cross_asset_projection(
                    concentrations, ticker, asset_class, own_dimensions=own_dimensions
                )
                steps.append(
                    E2EStep(
                        "cross_asset", "ok", f"concentrations={len(concentrations)}"
                    )
                )
            except Exception as exc:  # noqa: BLE001
                steps.append(
                    E2EStep("cross_asset", "error", f"{type(exc).__name__}: {exc}")
                )

        try:
            import datetime as _dt

            stages_ok = sum(1 for step in steps if step.status == "ok")
            self.bridge.sync_asset_frontmatter(
                ticker,
                asset_class,
                "scoring",
                {
                    "ticker": ticker.upper(),
                    "asset_class": asset_class,
                    "stages_ok": stages_ok,
                    # data de calendário, não timestamp
                    "as_of": _dt.date.today().isoformat(),  # noqa: DTZ011
                },
            )
        # summary frontmatter is best-effort, never masks the real per-stage results above
        except Exception:  # noqa: BLE001, S110
            pass

        return AssetE2EResult(
            ticker,
            template,
            analysis,
            valuation,
            concentrations,
            quantitative,
            tuple(steps),
        )

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
        market_inputs: Mapping[str, float | None] | None = None,
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
                market_inputs=market_inputs,
            )
            steps = tuple(
                (
                    E2EStep(
                        "quantitative",
                        "blocked",
                        f"NAV scale break requires normalization: {series.scale_breaks}",
                    )
                    if step.name == "quantitative"
                    else step
                )
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
            market_inputs=market_inputs,
        )
