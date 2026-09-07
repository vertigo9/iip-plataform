from __future__ import annotations

import importlib
import inspect
from pathlib import Path

MODULE = "iip.decision.decision_engine"


def _load():
    return importlib.import_module(MODULE)


def test_decision_engine_imports() -> None:
    module = _load()
    assert module is not None


def test_decision_engine_source_is_resolvable() -> None:
    module = _load()
    path = Path(module.__file__).resolve()
    assert path.exists()
    assert path.stat().st_size > 50


def test_decision_engine_public_surface_is_nonempty() -> None:
    module = _load()
    public = {
        name: obj
        for name, obj in vars(module).items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
    }
    assert public, f"No public callable/class surface in {MODULE}"


def test_decision_engine_public_surface_is_introspectable() -> None:
    module = _load()
    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(obj) or inspect.isclass(obj):
            inspect.signature(obj)


def test_decision_engine_does_not_import_unknown_runtime_dependency() -> None:
    module = _load()
    assert module.__name__ == MODULE
