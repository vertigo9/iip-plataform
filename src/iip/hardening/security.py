"""Security and guardrail contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityCheck:
    name: str
    passed: bool
    severity: str


def guard(name: str, passed: bool, severity: str = "high") -> SecurityCheck:
    return SecurityCheck(name, bool(passed), severity)


def all_passed(checks: tuple[SecurityCheck, ...]) -> bool:
    return bool(checks) and all(check.passed for check in checks)
