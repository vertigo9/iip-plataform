"""Testes unitários para a geração do Dashboard Consolidado no Obsidian."""

import tempfile
from pathlib import Path

from iip.obsidian.dashboard import generate_portfolio_dashboard


def test_generate_portfolio_dashboard():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        dashboard_file = generate_portfolio_dashboard(vault)

        assert dashboard_file.exists()
        assert dashboard_file == vault / "02_Portfolio" / "Dashboard.md"
        content = dashboard_file.read_text(encoding="utf-8")
        assert "Dashboard Consolidado" in content
        assert "<!-- IIP:BEGIN:METRICS_SUMMARY -->" in content
        assert "dataviewjs" in content
        assert 'dv.pages(\'"01_Assets"\')' in content


def test_generate_portfolio_dashboard_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        first = generate_portfolio_dashboard(vault)
        second = generate_portfolio_dashboard(vault)

        assert first == second
        assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")