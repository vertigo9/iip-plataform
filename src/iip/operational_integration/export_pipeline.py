"""Export pipeline for consolidated portfolio reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExportArtifact:
    format: str
    name: str
    payload: Any


class ExportPipeline:
    def __init__(self, exporters: dict[str, Callable[[Any], Any]]) -> None:
        self.exporters = dict(exporters)

    def export(self, fmt: str, name: str, payload: Any) -> ExportArtifact:
        exporter = self.exporters.get(fmt.lower())
        if exporter is None:
            raise ValueError(f"unsupported_format:{fmt}")
        return ExportArtifact(fmt.lower(), name, exporter(payload))
