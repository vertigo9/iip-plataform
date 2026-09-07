from __future__ import annotations

import importlib
import os
import urllib.request
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]

# These are read-only/import-only production surfaces already exercised by the
# certified RC test tree. The smoke test deliberately avoids data mutation.
CORE_MODULES = (
    "iip.decision.decision_engine",
    "iip.decision.validation",
    "iip.decision.valuation_bridge",
    "iip.knowledge.repository",
    "iip.knowledge.vault",
    "iip.operational.quality",
    "iip.health",
)


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_production_core_imports(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


def test_project_root_and_src_exist() -> None:
    assert PROJECT.exists()
    assert (PROJECT / "src").exists()


def test_production_health_endpoint_when_configured() -> None:
    # HTTP production smoke is intentionally opt-in. This test file is also
    # imported by the broad integrated regression, where external HTTP checks
    # must not leak into the test environment.
    run_http = os.getenv("IIP_RUN_PROD_HTTP_SMOKE", "").strip().lower()
    if run_http not in {"1", "true", "yes"}:
        pytest.skip(
            "IIP_RUN_PROD_HTTP_SMOKE nÃ£o habilitado; health HTTP reservado "
            "ao Production Smoke Gate standalone."
        )

    url = os.getenv("IIP_PROD_HEALTH_URL")
    if not url:
        pytest.skip("IIP_PROD_HEALTH_URL nÃ£o configurada; smoke HTTP nÃ£o executado.")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "IIP-Production-Smoke/1.0"},
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        assert 200 <= response.status < 400


def test_production_environment_marker_when_configured() -> None:
    env = os.getenv("IIP_ENVIRONMENT")
    if not env:
        pytest.skip("IIP_ENVIRONMENT nÃ£o configurada.")
    assert env.lower() in {"prod", "production"}
