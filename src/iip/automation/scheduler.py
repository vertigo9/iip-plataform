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
) -> dict[str, Any]:
    """Executa a esteira automatizada completa: colheita, decisão e atualização de dashboard."""
    logger.info("Iniciando esteira automatizada de carteira...")
    cycle_results = run_portfolio_cycle(manifest)
    
    dashboard_path = generate_portfolio_dashboard(vault_path)
    logger.info("Esteira automatizada concluída. Dashboard gerado em: %s", dashboard_path)

    return {
        "processed": cycle_results.get("processed", 0),
        "errors": cycle_results.get("errors", 0),
        "dashboard_path": str(dashboard_path),
    }