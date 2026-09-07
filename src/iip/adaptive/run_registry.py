"""Run registry for resumable operational cycles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunState:
    run_id: str
    status: str
    completed_assets: tuple[str, ...] = ()


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}

    def start(self, run_id: str) -> RunState:
        state = RunState(run_id, "running", ())
        self._runs[run_id] = state
        return state

    def checkpoint(self, run_id: str, ticker: str) -> RunState:
        current = self._runs.get(run_id, RunState(run_id, "running", ()))
        assets = tuple(dict.fromkeys((*current.completed_assets, ticker.upper())))
        state = RunState(run_id, "running", assets)
        self._runs[run_id] = state
        return state

    def complete(self, run_id: str) -> RunState:
        current = self._runs[run_id]
        state = RunState(run_id, "complete", current.completed_assets)
        self._runs[run_id] = state
        return state

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)
