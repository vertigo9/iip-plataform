from __future__ import annotations

import importlib
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "src"

TARGETS = {
    "decision_engine": "iip.decision.decision_engine",
    "document_classification": "iip.intelligence.document_classification",
    "operational_quality": "iip.operational.quality",
    "knowledge_repository": "iip.knowledge.repository",
}


@pytest.mark.parametrize("name", tuple(TARGETS))
def test_target_module_imports(name: str) -> None:
    module_name = TARGETS[name]
    assert importlib.import_module(module_name) is not None


@pytest.mark.parametrize("name", tuple(TARGETS))
def test_target_module_has_source(name: str) -> None:
    module = importlib.import_module(TARGETS[name])
    path = Path(module.__file__)
    source = path.read_text(encoding="utf-8", errors="ignore")
    assert source.strip()
    assert ("def " in source) or ("class " in source)


def test_critical_targets_live_under_src() -> None:
    for module_name in TARGETS.values():
        path = Path(importlib.import_module(module_name).__file__).resolve()
        assert str(path).startswith(str(SRC.resolve()))


def test_critical_path_import_matrix() -> None:
    imported = [importlib.import_module(name).__name__ for name in TARGETS.values()]
    assert sorted(imported) == sorted(TARGETS.values())
