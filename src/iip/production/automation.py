"""Deterministic automation orchestration for IIP production workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    READY = "ready"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class JobSpec:
    name: str
    handler: Callable[..., Any]
    enabled: bool = True


@dataclass(frozen=True)
class JobResult:
    name: str
    status: JobStatus
    value: Any = None
    error: str | None = None


class JobRunner:
    def __init__(self, jobs: tuple[JobSpec, ...] = ()) -> None:
        self.jobs = {job.name: job for job in jobs}

    def run(self, name: str, *args, **kwargs) -> JobResult:
        job = self.jobs.get(name)
        if job is None:
            return JobResult(name, JobStatus.SKIPPED, error="job_not_registered")
        if not job.enabled:
            return JobResult(name, JobStatus.SKIPPED, error="job_disabled")
        try:
            return JobResult(name, JobStatus.SUCCESS, job.handler(*args, **kwargs))
        except Exception as exc:  # noqa: BLE001 — isola falha do job num JobResult, nao deixa propagar
            return JobResult(
                name, JobStatus.FAILED, error=f"{type(exc).__name__}:{exc}"
            )
