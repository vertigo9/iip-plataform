"""Render an IncomeForecast into the note content projected onto the
asset's scoring section, alongside the opportunity score and monthly
contribution priority.
"""

from __future__ import annotations

from iip.portfolio_data.income_forecast import IncomeForecast


def format_income_forecast_note(forecast: IncomeForecast) -> str:
    periods = ", ".join(forecast.periods_used)
    return (
        f"- **Projeção próxima distribuição:** R$ {forecast.projected_amount_per_unit:.2f}/cota\n"
        f"- Método: média móvel de {forecast.sample_size} mês(es) "
        f"(janela configurada: {forecast.window})\n"
        f"- Períodos usados: {periods}"
    )
