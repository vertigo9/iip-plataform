"""Testes unitários para a geração do Dashboard Consolidado no Obsidian."""

import tempfile
from pathlib import Path

from iip.obsidian.dashboard import generate_portfolio_dashboard


def test_generate_portfolio_dashboard():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        dashboard_file = generate_portfolio_dashboard(vault)

        assert dashboard_file.exists()
        content = dashboard_file.read_text(encoding="utf-8")
        assert "Visão Geral do Portfolio — IIP Engine" in content
        assert "<!-- IIP:BEGIN:METRICS_SUMMARY -->" in content
        assert "dataviewjs" in content