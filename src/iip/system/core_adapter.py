"""Core/CLI safe adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    command: str
    success: bool
    value: Any = None
    error: str | None = None


class CoreCommandAdapter:
    """Translate a command into an injected callable without hidden I/O."""

    def __init__(self, commands: dict[str, Callable[..., Any]] | None = None) -> None:
        self.commands = dict(commands or {})

    def execute(self, command: str, *args, **kwargs) -> CommandResult:
        handler = self.commands.get(command)
        if handler is None:
            return CommandResult(command, False, error="unknown_command")
        try:
            return CommandResult(command, True, handler(*args, **kwargs))
        except Exception as exc:  # noqa: BLE001 — isola falha do handler num CommandResult, nao deixa propagar
            return CommandResult(command, False, error=f"{type(exc).__name__}:{exc}")
