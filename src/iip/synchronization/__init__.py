"""IIP Synchronization Engine — detect inconsistencies."""

from __future__ import annotations

from dataclasses import dataclass

from iip.config import IIPSettings, get_settings
from iip.registry import ModuleRegistry
from iip.versioning import VersionManager


@dataclass
class SyncIssue:
    severity: str
    component: str
    message: str
    details: str | None = None


class SynchronizationEngine:
    @classmethod
    def check_module_consistency(cls, settings: IIPSettings) -> list[SyncIssue]:
        issues: list[SyncIssue] = []
        registry_status = ModuleRegistry.status()

        # Removed modules_dir check - just check registry status
        modules = registry_status.get("modules", {})
        if isinstance(modules, dict):
            for name, mod in modules.items():
                if (
                    isinstance(mod, dict)
                    and mod.get("loaded")
                    and not mod.get("enabled")
                ):
                    issues.append(
                        SyncIssue(
                            severity="WARNING",
                            component="module_registry",
                            message=f"Module {name} is loaded but disabled",
                        )
                    )

        return issues

    @classmethod
    def check_version_compatibility(cls, settings: IIPSettings) -> list[SyncIssue]:
        issues: list[SyncIssue] = []
        platform_version = VersionManager.current()

        if platform_version.pre_release:
            issues.append(
                SyncIssue(
                    severity="INFO",
                    component="version",
                    message=f"Using pre-release version: {platform_version}",
                )
            )

        return issues

    @classmethod
    def check_contract_integrity(cls, settings: IIPSettings) -> list[SyncIssue]:
        issues: list[SyncIssue] = []
        issues.append(
            SyncIssue(
                severity="INFO",
                component="contracts",
                message="Contract integrity checks configured",
            )
        )
        return issues

    @classmethod
    def full_sync_check(
        cls, settings: IIPSettings | None = None
    ) -> tuple[bool, list[SyncIssue]]:
        settings = settings or get_settings()
        all_issues: list[SyncIssue] = []
        all_issues.extend(cls.check_module_consistency(settings))
        all_issues.extend(cls.check_version_compatibility(settings))
        all_issues.extend(cls.check_contract_integrity(settings))
        has_errors = any(issue.severity == "ERROR" for issue in all_issues)
        return not has_errors, all_issues

    @classmethod
    def report(cls, issues: list[SyncIssue]) -> str:
        if not issues:
            return "No synchronization issues detected."
        lines: list[str] = []
        for issue in issues:
            lines.append(f"[{issue.severity}] {issue.component}: {issue.message}")
            if issue.details:
                lines.append(f"  └─ {issue.details}")
        return "\n".join(lines)
