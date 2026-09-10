import pytest

from iip.portfolio_data.income_forecast import (
    IncomeForecast,
    MonthlyDistribution,
    forecast_next_distribution,
)


def make_history(*amounts: float, start_year: int = 2026, start_month: int = 1):
    result = []
    year, month = start_year, start_month
    for amount in amounts:
        result.append(MonthlyDistribution(f"{year:04d}-{month:02d}", amount))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return tuple(result)


def test_forecast_averages_last_window_months():
    # jan=1.00, fev=0.80, mar=0.90 -> average of last 3 = 0.90
    history = make_history(1.00, 0.80, 0.90)

    forecast = forecast_next_distribution("pcip11", history, window=3)

    assert isinstance(forecast, IncomeForecast)
    assert forecast.ticker == "PCIP11"
    assert forecast.method == "moving_average_3m"
    assert forecast.window == 3
    assert forecast.sample_size == 3
    assert forecast.periods_used == ("2026-01", "2026-02", "2026-03")
    assert forecast.projected_amount_per_unit == 0.9


def test_forecast_uses_only_the_most_recent_window():
    # 5 months; window=3 should use only the last 3 (0.90, 0.89, 0.89) -> avg 0.893333...
    history = make_history(1.00, 0.80, 0.90, 0.89, 0.89)

    forecast = forecast_next_distribution("PCIP11", history, window=3)

    assert forecast.sample_size == 3
    assert forecast.periods_used == ("2026-03", "2026-04", "2026-05")
    assert forecast.projected_amount_per_unit == round((0.90 + 0.89 + 0.89) / 3, 12)


def test_forecast_reports_true_sample_size_when_history_shorter_than_window():
    history = make_history(1.00, 0.80)  # only 2 months, window=6

    forecast = forecast_next_distribution("PCIP11", history, window=6)

    assert forecast.window == 6
    assert forecast.sample_size == 2  # never claims 6 when only 2 exist
    assert forecast.method == "moving_average_6m"
    assert forecast.projected_amount_per_unit == 0.9


def test_forecast_sorts_out_of_order_history_chronologically():
    history = (
        MonthlyDistribution("2026-03", 0.90),
        MonthlyDistribution("2026-01", 1.00),
        MonthlyDistribution("2026-02", 0.80),
    )

    forecast = forecast_next_distribution("PCIP11", history, window=3)

    assert forecast.periods_used == ("2026-01", "2026-02", "2026-03")


def test_forecast_rejects_empty_history():
    with pytest.raises(ValueError):
        forecast_next_distribution("PCIP11", (), window=3)


def test_forecast_rejects_non_positive_window():
    history = make_history(1.00)
    with pytest.raises(ValueError):
        forecast_next_distribution("PCIP11", history, window=0)


def test_forecast_rejects_duplicate_periods():
    history = (
        MonthlyDistribution("2026-01", 1.00),
        MonthlyDistribution("2026-01", 0.80),
    )
    with pytest.raises(ValueError):
        forecast_next_distribution("PCIP11", history, window=3)
