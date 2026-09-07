"""Canonical full-system export adapter."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class SystemExportAdapter:
    def export(self, value: Any) -> dict[str, Any]:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return dict(value)
        raise TypeError("unsupported_export_type")
