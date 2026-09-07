"""Cross-layer contract validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractCheck:
    name: str
    passed: bool
    detail: str = ""


def check_nonempty(name: str, value) -> ContractCheck:
    return ContractCheck(name, bool(value), "" if value else "empty")


def check_version(current: int, minimum: int) -> ContractCheck:
    return ContractCheck(
        "version",
        current >= minimum,
        "" if current >= minimum else f"below_minimum:{minimum}",
    )
