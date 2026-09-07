"""Portable export contract for reports and checkpoints."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def serialize(value: Any) -> dict[str, Any]:
    if not is_dataclass(value):
        raise TypeError("value must be a dataclass")
    return asdict(value)
