from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
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
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
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
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
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
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
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
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
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
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class SynchronizationHealthCheck:
    @property
    def name(self) -> str:
        return "synchronization"

    def check(self, settings: IIPSettings) -> HealthResult:
        try:
            from iip.synchronization import SynchronizationEngine

            ok, issues = SynchronizationEngine.full_sync_check(settings)

            # Informational SyncIssue entries are diagnostic messages, not
            # synchronization problems. Only WARNING/ERROR entries should
            # be reported as issues by the health check.
            problem_issues = [
                issue
                for issue in issues
                if str(getattr(issue, "severity", "")).upper()
                not in {"INFO", "INFORMATIONAL"}
            ]

            if not problem_issues:
                message = "No synchronization issues detected"
            else:
                message = f"{len(problem_issues)} sync issues detected"

            return HealthResult(
                name=self.name,
                healthy=ok,
                message=message,
            )
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
            return HealthResult(name=self.name, healthy=False, message=str(exc))


class DataSourceReachabilityCheck:
    """Lightweight connectivity check for an external data source — a
    HEAD request with a short timeout, NOT a real data fetch. Exists to
    answer "is this source even reachable right now" cheaply; some of
    our real datasets are tens of MB, far too slow for a routine health
    check.

    "Healthy" here means "the server responded at all" — even a 404 or
    405 on a bare HEAD to the domain root counts, since the failure mode
    this exists to catch is DNS/connection/timeout, not "is this exact
    endpoint valid". A source that has genuinely changed its API shape
    (like FNET's search resisting automation, found earlier in this
    project) would still show "healthy" here — this check is a first
    filter for "totally unreachable", not a substitute for the harvester
    tests that verify real parsing.
    """

    def __init__(
        self,
        source_name: str,
        url: str,
        *,
        timeout: float = 5.0,
        opener=None,
    ) -> None:
        self._source_name = source_name
        self._url = url
        self._timeout = timeout
        self._opener = opener or urlopen

    @property
    def name(self) -> str:
        return f"source_{self._source_name}"

    def check(self, settings: IIPSettings) -> HealthResult:
        request = Request(
            self._url,
            headers={"User-Agent": "IIP-D-OBSIDIAN/1.0"},
            method="HEAD",
        )
        try:
            response = self._opener(request, timeout=self._timeout)
            status = getattr(response, "status", 200)
            return HealthResult(name=self.name, healthy=True, message=f"HTTP {status}")
        except HTTPError as exc:
            # The server answered — just not with 2xx/3xx to a bare
            # HEAD. That still means it's reachable.
            return HealthResult(
                name=self.name,
                healthy=True,
                message=f"HTTP {exc.code} (respondeu, servidor no ar)",
            )
        except URLError as exc:
            return HealthResult(
                name=self.name, healthy=False, message=f"Inalcançável: {exc.reason}"
            )
        # health check isolado nao pode derrubar os demais
        except Exception as exc:  # noqa: BLE001
            return HealthResult(name=self.name, healthy=False, message=str(exc))


def default_data_source_checks() -> tuple[DataSourceReachabilityCheck, ...]:
    """One reachability check per real external data source this
    project integrates with. Kept as a single list here so adding a new
    source's check is one line, not a hunt through the CLI."""
    return (
        DataSourceReachabilityCheck("cvm", "https://dados.cvm.gov.br"),
        DataSourceReachabilityCheck("bacen", "https://api.bcb.gov.br"),
        DataSourceReachabilityCheck("ibge", "https://servicodados.ibge.gov.br"),
        DataSourceReachabilityCheck("bolsai", "https://api.usebolsai.com"),
        DataSourceReachabilityCheck("brapi", "https://brapi.dev"),
        DataSourceReachabilityCheck("brasilapi", "https://brasilapi.com.br"),
        DataSourceReachabilityCheck("mziq", "https://apicatalog.mziq.com"),
    )


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
            # health check isolado nao pode derrubar os demais
            except Exception as exc:  # noqa: BLE001
                results.append(
                    HealthResult(
                        name=getattr(check, "name", "unknown"),
                        healthy=False,
                        message=f"Check failed: {exc}",
                    )
                )
        return SystemHealth(checks=results)
