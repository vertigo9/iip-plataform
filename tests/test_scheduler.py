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


def test_execute_scheduled_pipeline_can_refresh_registered_portfolio(tmp_path):
    calls = []

    class RefreshResult:
        pass

    def refresh_fn(output_dir, *, bolsai_api_key, brapi_token):
        calls.append((output_dir, bolsai_api_key, brapi_token))
        return RefreshResult()

    result = execute_scheduled_pipeline(
        [],
        tmp_path,
        refresh_registered=True,
        refresh_fn=refresh_fn,
    )

    assert result["refresh"] is not None
    assert calls[0][0] == tmp_path / "portfolio_snapshots"