"""Idempotent recovery contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryState:
    run_id: str
    completed_steps: tuple[str, ...]


class RecoveryStore:
    def __init__(self) -> None:
        self._runs: dict[str, RecoveryState] = {}

    def checkpoint(self, run_id: str, step: str) -> RecoveryState:
        current = self._runs.get(run_id, RecoveryState(run_id, ()))
        steps = tuple(dict.fromkeys((*current.completed_steps, step)))
        state = RecoveryState(run_id, steps)
        self._runs[run_id] = state
        return state

    def is_completed(self, run_id: str, step: str) -> bool:
        state = self._runs.get(run_id)
        return bool(state and step in state.completed_steps)
