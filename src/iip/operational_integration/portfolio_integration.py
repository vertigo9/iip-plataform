"""Operational integration facade over existing portfolio capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IntegrationResult:
    component: str
    success: bool
    value: Any = None
    error: str | None = None


class PortfolioIntegrationFacade:
    COMPONENTS = (
        "registry",
        "source_policy",
        "source_router",
        "pipeline",
        "validation",
        "health",
    )

    def __init__(self, handlers: dict[str, Callable[..., Any]]) -> None:
        self.handlers = dict(handlers)

    def execute(self, component: str, *args, **kwargs) -> IntegrationResult:
        handler = self.handlers.get(component)
        if handler is None:
            return IntegrationResult(component, False, error="component_not_registered")
        try:
            return IntegrationResult(component, True, handler(*args, **kwargs))
        # isola falha do handler num IntegrationResult, nao deixa propagar
        except Exception as exc:  # noqa: BLE001
            return IntegrationResult(
                component, False, error=f"{type(exc).__name__}:{exc}"
            )
