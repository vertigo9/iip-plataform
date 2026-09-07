"""User-facing service contracts for IIP portfolio intelligence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServiceResponse:
    ok: bool
    operation: str
    payload: Any = None
    error: str | None = None


class PortfolioService:
    def __init__(self, handlers: dict[str, Callable[..., Any]]) -> None:
        self.handlers = dict(handlers)

    def execute(self, operation: str, **params) -> ServiceResponse:
        handler = self.handlers.get(operation)
        if handler is None:
            return ServiceResponse(False, operation, error="operation_not_supported")
        try:
            return ServiceResponse(True, operation, payload=handler(**params))
        except Exception as exc:
            return ServiceResponse(
                False,
                operation,
                error=f"{type(exc).__name__}:{exc}",
            )
