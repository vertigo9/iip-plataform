"""CLI adapter for core portfolio operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CliResponse:
    exit_code: int
    message: str


def handle(command: str, *, available: tuple[str, ...]) -> CliResponse:
    if command not in available:
        return CliResponse(2, f"unknown_command:{command}")
    return CliResponse(0, f"ok:{command}")
