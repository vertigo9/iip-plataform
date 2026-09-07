"""Hardening adapters for core execution contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CoreResult:
    ok: bool
    operation: str
    value: Any = None
    error: str | None = None


class CoreAdapter:
    def __init__(self, operations: dict[str, Callable[..., Any]]) -> None:
        self.operations = dict(operations)

    def run(self, operation: str, *args, **kwargs) -> CoreResult:
        fn = self.operations.get(operation)
        if fn is None:
            return CoreResult(False, operation, error="unsupported_operation")
        try:
            return CoreResult(True, operation, fn(*args, **kwargs))
        except Exception as exc:
            return CoreResult(False, operation, error=f"{type(exc).__name__}:{exc}")
