"""Deep export adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ExportResult:
    format: str
    payload: str


def to_json(value) -> ExportResult:
    return ExportResult("json", json.dumps(value, ensure_ascii=False, sort_keys=True))


def to_text(value) -> ExportResult:
    return ExportResult("text", str(value))


def export(fmt: str, value) -> ExportResult:
    normalized = fmt.lower()
    if normalized == "json":
        return to_json(value)
    if normalized == "text":
        return to_text(value)
    raise ValueError(f"unsupported_format:{fmt}")
