"""Versioned model registry with explicit promotion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelVersion:
    name: str
    version: str
    checksum: str
    production: bool = False


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[tuple[str, str], ModelVersion] = {}

    def register(self, model: ModelVersion) -> None:
        self._models[(model.name, model.version)] = model

    def promote(self, name: str, version: str) -> bool:
        key = (name, version)
        model = self._models.get(key)
        if model is None:
            return False
        for k, item in tuple(self._models.items()):
            if item.name == name:
                self._models[k] = ModelVersion(
                    item.name, item.version, item.checksum, item.version == version
                )
        return True

    def get(self, name: str, version: str) -> ModelVersion | None:
        return self._models.get((name, version))
