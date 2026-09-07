from __future__ import annotations

import importlib
from pathlib import Path

import pytest

TARGETS = (
    "iip.decision.decision_engine",
    "iip.operational.quality",
    "iip.knowledge.repository",
    "iip.intelligence.document_classification",
)


@pytest.mark.parametrize("module_name", TARGETS)
def test_foundation_target_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


@pytest.mark.parametrize("module_name", TARGETS)
def test_foundation_target_source_exists(module_name: str) -> None:
    module = importlib.import_module(module_name)
    path = Path(module.__file__).resolve()
    assert path.exists()
    assert path.stat().st_size > 20


def test_foundation_import_matrix_is_complete() -> None:
    loaded = [importlib.import_module(name).__name__ for name in TARGETS]
    assert loaded == list(TARGETS)
