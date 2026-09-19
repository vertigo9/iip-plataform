from pathlib import Path

from iip.portfolio.e2e import AssetE2ERunner
from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
)
from iip.universal.portfolio_state import PortfolioState, PositionState


class FetchResult:
    warnings = ()


def template():
    return {
        "symbol": "BTCI11",
        "price": 8.36,
        "financials": {
            "assets_under_management_millions": 1003.96,
            "management_fee_ratio": 0.005,
            "occupancy_rate": 0.85,
            "payout_sustainability_score": 80,
        },
    }, FetchResult()


def state():
    return PortfolioState(
        as_of="2026-09-17",
        total_value=100000,
        positions=(
            PositionState(
                ticker="BTCI11",
                quantity=100,
                market_value=836,
                weight=0.00836,
                asset_class="fund",
                segment="Crédito Imobiliário",
                manager="BTG Pactual",
            ),
        ),
    )


def test_runner_executes_all_stages_when_inputs_are_available(tmp_path: Path):
    result = AssetE2ERunner(vault_path=str(tmp_path)).run(
        ticker="BTCI11",
        fetch_template=template,
        fair_value=10.0,
        portfolio_state=state(),
        historical_series=(8.1, 8.2, 8.3, 8.36),
    )

    assert result.succeeded
    assert {step.name for step in result.steps} == {
        "collection",
        "fundamental_analysis",
        "valuation",
        "quantitative",
        "cross_asset",
    }
    assert result.valuation.margin_of_safety == 0.196172248804
    assert result.quantitative is not None
    assert result.quantitative["observations"] == 4.0
    assert result.quantitative["total_return"] > 0
    assert result.concentrations
    assert list(tmp_path.rglob("*.md"))


def test_runner_reports_missing_inputs_without_fabricating_results(tmp_path: Path):
    result = AssetE2ERunner(vault_path=str(tmp_path)).run(
        ticker="BTCI11",
        fetch_template=template,
    )

    statuses = {step.name: step.status for step in result.steps}
    assert statuses["collection"] == "ok"
    assert statuses["fundamental_analysis"] == "ok"
    assert statuses["valuation"] == "blocked"
    assert statuses["quantitative"] == "blocked"
    assert statuses["cross_asset"] == "blocked"
    assert not result.succeeded


def test_runner_uses_persisted_series_and_blocks_scale_break(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path / "vault")
    store.save(
        HistoricalSeries(
            ticker="BTCI11",
            cnpj="09552812000114",
            provider="cvm",
            observations=(
                HistoricalObservation("2022-12-01", 1, 90.0, 0.01, 0.0, 1, 1, "doc-a", "hash-a", 2022),
                HistoricalObservation("2023-01-01", 1, 10.0, 0.01, 0.0, 1, 1, "doc-b", "hash-b", 2023),
            ),
            source_documents=(),
        )
    )

    result = AssetE2ERunner(vault_path=str(tmp_path / "vault")).run_with_persisted_series(
        ticker="BTCI11",
        fetch_template=template,
        series_store=store,
    )

    quantitative = next(step for step in result.steps if step.name == "quantitative")
    assert quantitative.status == "blocked"
    assert "scale break" in quantitative.detail
