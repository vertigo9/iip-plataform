from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from iip.config import IIPSettings
from iip.logging import get_logger

logger = get_logger(__name__)


class HealthCheck(Protocol):
    @property
    def name(self) -> str: ...
    def check(self, settings: IIPSettings) -> HealthResult: ...


@dataclass
class HealthResult:
    name: str
    healthy: bool
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SystemHealth:
    checks: list[HealthResult] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return all(c.healthy for c in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "healthy" if self.healthy else "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": [c.__dict__ for c in self.checks],
        }


class ConfigurationHealthCheck:
    @property
    def name(self) -> str:
        return "configuration"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            return HealthResult(
                name=self.name,
                healthy=bool(settings.app_name),
                message=f"Environment: {settings.environment.value}",
            )
        except Exception as exc:
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class FileSystemHealthCheck:
    @property
    def name(self) -> str:
        return "filesystem"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            return HealthResult(
                name=self.name,
                healthy=settings.base_dir.exists(),
                message=f"Base dir: {settings.base_dir}",
            )
        except Exception as exc:
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class PythonVersionHealthCheck:
    @property
    def name(self) -> str:
        return "python_version"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            version = sys.version_info
            return HealthResult(
                name=self.name,
                healthy=version >= (3, 12),
                message=f"Python {version.major}.{version.minor}.{version.micro}",
            )
        except Exception as exc:
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class ModuleCountHealthCheck:
    @property
    def name(self) -> str:
        return "module_registry"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            from iip.registry import ModuleRegistry

            status = ModuleRegistry.status()
            return HealthResult(
                name=self.name,
                healthy=True,
                message=f"{status.get('total', 0)} registered, {status.get('loaded', 0)} loaded",
            )
        except Exception as exc:
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class VersionCompatibilityHealthCheck:
    @property
    def name(self) -> str:
        return "version_compatibility"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            from iip.versioning import VersionManager

            return HealthResult(
                name=self.name,
                healthy=True,
                message=f"Platform version: {VersionManager.current()}",
            )
        except Exception as exc:
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class ReplicationStatusHealthCheck:
    @property
    def name(self) -> str:
        return "replication"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            from iip.replication import ReplicationEngine

            status = ReplicationEngine.status()
            return HealthResult(
                name=self.name,
                healthy=True,
                message=f"{status.get('replications_total', 0)} replications, {status.get('replications_certified', 0)} certified",
            )
        except Exception as exc:
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class SynchronizationHealthCheck:
    @property
    def name(self) -> str:
        return "synchronization"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            from iip.synchronization import SynchronizationEngine

            ok, issues = SynchronizationEngine.full_sync_check(settings)
            return HealthResult(
                name=self.name,
                healthy=ok,
                message=f"{len(issues)} sync issues detected",
            )
        except Exception as exc:
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class HealthEngine:
    def __init__(self, settings: IIPSettings) -> None:
        self._settings = settings
        self._checks: list[HealthCheck] = []

    def register(self, check: HealthCheck) -> None:
        self._checks.append(check)

    def run_all(self) -> SystemHealth:
        results: list[HealthResult] = []
        for check in self._checks:
            try:
                results.append(check.check(self._settings))
            except Exception as exc:
                results.append(
                    HealthResult(
                        name=getattr(check, "name", "unknown"),
                        healthy=False,
                        message=f"Check failed: {exc}",
                    )
                )
        return SystemHealth(checks=results)
