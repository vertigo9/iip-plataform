from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

TARGETS = (
    "iip.decision.decision_engine",
    "iip.intelligence.document_classification",
    "iip.operational.quality",
    "iip.knowledge.repository",
    "iip.knowledge.vault",
    "iip.health",
    "iip.production_integration.allocation_review",
)


@pytest.mark.parametrize("module_name", TARGETS)
def test_target_module_import(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


@pytest.mark.parametrize("module_name", TARGETS)
def test_target_module_has_testable_public_surface(module_name: str) -> None:
    module = importlib.import_module(module_name)
    public = [
        obj
        for name, obj in vars(module).items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
    ]
    assert public, f"No public callable/class surface found in {module_name}"


def test_target_modules_are_distinct_and_resolvable() -> None:
    resolved = []
    for module_name in TARGETS:
        module = importlib.import_module(module_name)
        path = Path(module.__file__).resolve()
        resolved.append(path)
        assert path.exists()
    assert len(set(resolved)) == len(TARGETS)


def test_target_sources_are_nontrivial() -> None:
    for module_name in TARGETS:
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding="utf-8", errors="ignore")
        assert len(source.strip()) > 20
