"""IIP Core Runtime."""

from __future__ import annotations

from dataclasses import dataclass

from iip.config import IIPSettings, get_settings
from iip.health import (
    ConfigurationHealthCheck,
    FileSystemHealthCheck,
    HealthEngine,
    SystemHealth,
)
from iip.knowledge import KnowledgeBridge
from iip.knowledge.event_adapter import KnowledgeEventAdapter
from iip.logging import get_logger, setup_logging

logger = get_logger(__name__)


@dataclass
class ApplicationContext:
    settings: IIPSettings
    health_engine: HealthEngine
    knowledge_bridge: KnowledgeBridge | None = None
    knowledge_adapter: KnowledgeEventAdapter | None = None
    started: bool = False

    def health(self) -> SystemHealth:
        return self.health_engine.run_all()


class Runtime:
    _instance: Runtime | None = None
    _context: ApplicationContext | None = None

    def __new__(cls) -> Runtime:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def start(cls) -> ApplicationContext:
        if cls._context is not None and cls._context.started:
            return cls._context
        settings = get_settings()
        setup_logging(settings)
        he = HealthEngine(settings)
        he.register(ConfigurationHealthCheck())
        he.register(FileSystemHealthCheck())
        bridge = KnowledgeBridge(str(settings.obsidian_vault))
        adapter = KnowledgeEventAdapter(bridge)
        adapter.register()
        ctx = ApplicationContext(
            settings=settings,
            health_engine=he,
            knowledge_bridge=bridge,
            knowledge_adapter=adapter,
            started=True,
        )
        cls._context = ctx
        return ctx

    @classmethod
    def stop(cls) -> None:
        if cls._context:
            if cls._context.knowledge_adapter:
                cls._context.knowledge_adapter.unregister()
            cls._context.started = False

    @classmethod
    def get_context(cls) -> ApplicationContext | None:
        return cls._context
