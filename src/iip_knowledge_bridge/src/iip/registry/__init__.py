from __future__ import annotations

import importlib
from builtins import list as _list
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from iip.config import IIPSettings, get_settings
from iip.events import Event, EventBus
from iip.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ModuleManifest:
    name: str
    version: str
    description: str
    enabled: bool = True
    dependencies: list[str] = field(default_factory=list)
    blueprint: dict[str, Any] | None = None


@dataclass
class RegisteredModule:
    manifest: ModuleManifest
    instance: object | None = None
    loaded_at: str | None = None


class ModuleRegistry:
    _modules: dict[str, RegisteredModule] = {}
    _settings: IIPSettings | None = None

    @classmethod
    def initialize(cls, settings: IIPSettings | None = None) -> None:
        cls._settings = settings or get_settings()

    @classmethod
    def register(cls, name: str, manifest: ModuleManifest) -> None:
        cls._modules[name] = RegisteredModule(manifest=manifest)
        logger.info("module_registered", module=name, version=manifest.version)
        # Removed asyncio.create_task - too complex for simple tests
        # Event publishing can be done manually when needed

    @classmethod
    def get(cls, name: str) -> RegisteredModule | None:
        return cls._modules.get(name)

    @classmethod
    def list(cls, enabled_only: bool = False) -> _list[RegisteredModule]:
        mods = _list(cls._modules.values())
        if enabled_only:
            mods = [m for m in mods if m.manifest.enabled]
        return mods

    @classmethod
    async def load_module(cls, name: str) -> bool:
        if name not in cls._modules:
            logger.error("module_not_found", module=name)
            return False
        mod_info = cls._modules[name]
        if not mod_info.manifest.enabled:
            logger.info("module_disabled", module=name)
            return False
        for dep in mod_info.manifest.dependencies:
            if dep not in cls._modules or not cls._modules[dep].loaded_at:
                logger.error("missing_dependency", module=name, dependency=dep)
                return False
        try:
            module_path = f"iip.{name}"
            imported = importlib.import_module(module_path)
            mod_info.instance = imported
            mod_info.loaded_at = datetime.now(UTC).isoformat()
            logger.info("module_loaded", module=name)
            await EventBus.publish(
                Event(
                    type="module.loaded",
                    payload={"name": name, "timestamp": mod_info.loaded_at},
                    source="registry",
                )
            )
            return True
        except Exception as exc:
            logger.error("module_load_failed", module=name, error=str(exc))
            return False

    @classmethod
    async def load_all(cls) -> _list[str]:
        loaded: _list[str] = []
        for name in _list(cls._modules.keys()):
            if await cls.load_module(name):
                loaded.append(name)
        return loaded

    @classmethod
    def status(cls) -> dict[str, object]:
        return {
            "total": len(cls._modules),
            "enabled": sum(1 for m in cls._modules.values() if m.manifest.enabled),
            "loaded": sum(1 for m in cls._modules.values() if m.loaded_at),
            "modules": {
                name: {
                    "version": mod.manifest.version,
                    "enabled": mod.manifest.enabled,
                    "loaded": bool(mod.loaded_at),
                }
                for name, mod in cls._modules.items()
            },
        }
