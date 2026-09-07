"""Deterministic scheduled portfolio jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    cadence: str
    enabled: bool = True


class JobScheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}

    def register(self, job: ScheduledJob) -> ScheduledJob:
        self._jobs[job.name] = job
        return job

    def due(self, cadence: str) -> tuple[ScheduledJob, ...]:
        return tuple(
            job
            for job in sorted(self._jobs.values(), key=lambda item: item.name)
            if job.enabled and job.cadence == cadence
        )
