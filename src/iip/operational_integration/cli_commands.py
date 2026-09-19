"""CLI command dispatch for operational portfolio actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandOutcome:
    command: str
    success: bool
    payload: Any = None
    error: str | None = None


class CommandDispatcher:
    def __init__(self, commands: dict[str, Callable[..., Any]]) -> None:
        self.commands = dict(commands)

    def dispatch(self, command: str, *args, **kwargs) -> CommandOutcome:
        fn = self.commands.get(command)
        if fn is None:
            return CommandOutcome(command, False, error="unknown_command")
        try:
            return CommandOutcome(command, True, fn(*args, **kwargs))
        # isola falha do comando num CommandOutcome, nao deixa propagar
        except Exception as exc:  # noqa: BLE001
            return CommandOutcome(command, False, error=f"{type(exc).__name__}:{exc}")
