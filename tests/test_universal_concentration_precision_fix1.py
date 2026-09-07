from iip.universal.concentration import (
    all_concentrations,
    concentration,
    concentration_alerts,
)
from iip.universal.portfolio_state import PortfolioState, PositionState
from iip.universal.snapshot_diff import diff


def make_state():
    positions = (
        PositionState(
            "HGRU11",
            100,
            1000,
            0.25,
            "fund",
            "Tijolo",
            "Renda Urbana",
            "Patria",
            "Baixo",
        ),
        PositionState(
            "LVBI11", 100, 1000, 0.25, "fund", "Tijolo", "Logística", "Patria", "Baixo"
        ),
        PositionState("CPFE3", 50, 1000, 0.25, "equity"),
        PositionState("SCHD", 20, 1000, 0.25, "etf"),
    )
    return PortfolioState("2026-08-29", positions, 4000)


def test_alert_function_still_returns_only_breaches():
    result = concentration_alerts(make_state().positions, manager_limit=0.20)
    assert result[0].value == "Patria"
    assert result[0].breached


def test_all_concentration_dimensions_contains_exposure_even_below_limit():
    result = all_concentrations(make_state().positions)
    assert any(item.dimension == "manager" for item in result)
    assert any(item.dimension == "asset_class" for item in result)


def test_concentration_weights_are_normalized():
    result = concentration(
        make_state().positions,
        "asset_class",
        0.50,
        include_below_limit=True,
    )
    assert any(item.value == "fund" and item.weight == 0.50 for item in result)


def test_snapshot_diff_uses_decimal_stable_rounding():
    previous = make_state()
    current = PortfolioState(
        "2026-09-01",
        previous.positions[:2] + (PositionState("CPFE3", 50, 800, 0.20, "equity"),),
        4000,
    )
    result = diff(previous, current)
    cpfe = next(item for item in result if item.ticker == "CPFE3")
    schd = next(item for item in result if item.ticker == "SCHD")
    assert cpfe.change == -0.05
    assert schd.current_weight is None
