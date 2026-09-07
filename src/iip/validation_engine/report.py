"""Human-readable validation report."""

from __future__ import annotations

from .models import ValidationSummary


def render(summary: ValidationSummary) -> str:
    return "\n".join(
        (
            f"observations={summary.observations}",
            f"hit_rate={summary.hit_rate:.2%}",
            f"average_return={summary.average_return:.2%}",
            f"average_income={summary.average_income:.2%}",
            f"max_drawdown={summary.max_drawdown:.2%}",
            f"stress_hit_rate={summary.stress_hit_rate:.2%}",
        )
    )
