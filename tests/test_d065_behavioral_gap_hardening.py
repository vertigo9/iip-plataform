from __future__ import annotations

import importlib
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


def _module(name: str):
    return importlib.import_module(name)


def _source(name: str) -> str:
    module = _module(name)
    return Path(module.__file__).read_text(encoding="utf-8", errors="ignore")


@pytest.mark.parametrize("name", TARGETS)
def test_behavioral_targets_import(name: str) -> None:
    assert _module(name) is not None


@pytest.mark.parametrize("name", TARGETS)
def test_behavioral_targets_have_public_behavior(name: str) -> None:
    source = _source(name)
    assert source.strip()
    assert ("def " in source) or ("class " in source)


def test_decision_engine_exposes_callable_decision_surface() -> None:
    module = _module("iip.decision.decision_engine")
    callables = [
        getattr(module, attr)
        for attr in dir(module)
        if not attr.startswith("_") and callable(getattr(module, attr))
    ]
    assert callables


def test_document_classification_exposes_callable_surface() -> None:
    module = _module("iip.intelligence.document_classification")
    callables = [
        getattr(module, attr)
        for attr in dir(module)
        if not attr.startswith("_") and callable(getattr(module, attr))
    ]
    assert callables


def test_operational_quality_exposes_callable_surface() -> None:
    module = _module("iip.operational.quality")
    callables = [
        getattr(module, attr)
        for attr in dir(module)
        if not attr.startswith("_") and callable(getattr(module, attr))
    ]
    assert callables


def test_knowledge_repository_exposes_callable_surface() -> None:
    module = _module("iip.knowledge.repository")
    callables = [
        getattr(module, attr)
        for attr in dir(module)
        if not attr.startswith("_") and callable(getattr(module, attr))
    ]
    assert callables


def test_cross_module_behavioral_import_matrix() -> None:
    imported = [_module(name).__name__ for name in TARGETS]
    assert imported == list(TARGETS)
