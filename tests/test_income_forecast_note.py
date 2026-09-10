from iip.decision.income_forecast_note import format_income_forecast_note
from iip.portfolio_data.income_forecast import IncomeForecast


def test_format_income_forecast_note_includes_all_components():
    forecast = IncomeForecast(
        ticker="PCIP11",
        method="moving_average_3m",
        window=3,
        sample_size=3,
        periods_used=("2026-05", "2026-06", "2026-07"),
        projected_amount_per_unit=0.986667,
    )

    note = format_income_forecast_note(forecast)

    assert "0.99" in note
    assert "3 mês(es)" in note
    assert "janela configurada: 3" in note
    assert "2026-05, 2026-06, 2026-07" in note


def test_format_income_forecast_note_reflects_partial_sample():
    forecast = IncomeForecast(
        ticker="PCIP11",
        method="moving_average_6m",
        window=6,
        sample_size=2,
        periods_used=("2026-06", "2026-07"),
        projected_amount_per_unit=0.945,
    )

    note = format_income_forecast_note(forecast)

    assert "2 mês(es)" in note
    assert "janela configurada: 6" in note
