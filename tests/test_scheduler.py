"""Testes unitários para o orquestrador de automação do IIP."""

import tempfile
from pathlib import Path

from iip.automation.scheduler import execute_scheduled_pipeline


def test_execute_scheduled_pipeline():
    manifest = [
        {
            "ticker": "HGLG11",
            "asset_class": "FII",
            "metrics": {"VP_COTA": 150.5},
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        result = execute_scheduled_pipeline(manifest, tmpdir)
        assert result["processed"] == 1
        assert result["errors"] == 0
        assert Path(result["dashboard_path"]).exists()