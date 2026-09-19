"""Módulo de automação e agendamento de jobs do IIP Engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from iip.obsidian.dashboard import generate_portfolio_dashboard
from iip.operational.portfolio_runner import run_portfolio_cycle

logger = logging.getLogger(__name__)


def execute_scheduled_pipeline(
    manifest: list[dict[str, Any]],
    vault_path: Path | str,
    *,
    refresh_registered: bool = False,
    refresh_fn=None,
) -> dict[str, Any]:
    """Execute the legacy cycle and optionally refresh the real portfolio registry.

    The registered refresh reuses ``iip.portfolio.refresh.refresh_portfolio``;
    it does not route through the synthetic manifest cycle.
    """
    logger.info("Iniciando esteira automatizada de carteira...")
    cycle_results = run_portfolio_cycle(manifest)

    refresh_results = None
    if refresh_registered:
        from iip.config import get_settings
        from iip.portfolio.refresh import refresh_portfolio

        settings = get_settings()
        refresh_fn = refresh_fn or refresh_portfolio
        unwrap = lambda value: (
            value.get_secret_value()
            if value is not None and hasattr(value, "get_secret_value")
            else value
        )
        refresh_results = refresh_fn(
            Path(vault_path) / "portfolio_snapshots",
            bolsai_api_key=unwrap(settings.bolsai_api_key),
            brapi_token=unwrap(settings.brapi_token),
        )

    dashboard_path = generate_portfolio_dashboard(vault_path)
    logger.info(
        "Esteira automatizada concluída. Dashboard gerado em: %s", dashboard_path
    )

    return {
        "processed": cycle_results.get("processed", 0),
        "errors": cycle_results.get("errors", 0),
        "dashboard_path": str(dashboard_path),
        "refresh": refresh_results,
    }
