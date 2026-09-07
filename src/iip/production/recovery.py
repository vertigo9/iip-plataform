"""Recovery and retry policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 2
    backoff_seconds: float = 1.0


def should_retry(attempt: int, policy: RetryPolicy) -> bool:
    if policy.attempts < 1:
        return False
    return attempt < policy.attempts
