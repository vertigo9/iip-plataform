"""IIP Version Manager — semantic versioning and compatibility."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Version:
    """Semantic version representation."""

    major: int
    minor: int
    patch: int
    pre_release: str | None = None

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            return f"{base}-{self.pre_release}"
        return base

    @classmethod
    def parse(cls, version_str: str) -> Version:
        """Parse version string like '0.1.0-alpha'."""
        parts = version_str.split("-")
        core = parts[0]
        pre = parts[1] if len(parts) > 1 else None

        nums = [int(x) for x in core.split(".")]
        return cls(major=nums[0], minor=nums[1], patch=nums[2], pre_release=pre)

    def __lt__(self, other: Version) -> bool:
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        if self.pre_release and not other.pre_release:
            return True
        if not self.pre_release and other.pre_release:
            return False
        if self.pre_release and other.pre_release:
            return self.pre_release < other.pre_release
        return False


@dataclass
class CompatibilityMatrix:
    """Defines which versions are compatible."""

    minimum_major: int = 0
    minimum_minor: int = 0
    maximum_major: int | None = None
    maximum_minor: int | None = None


class VersionManager:
    """Manages platform versions and compatibility."""

    _current_version: Version = Version.parse("0.1.0-alpha")
    _matrix: CompatibilityMatrix = CompatibilityMatrix()

    @classmethod
    def current(cls) -> Version:
        """Return current platform version."""
        return cls._current_version

    @classmethod
    def bump_major(cls) -> None:
        cls._current_version.major += 1
        cls._current_version.minor = 0
        cls._current_version.patch = 0
        cls._current_version.pre_release = None

    @classmethod
    def bump_minor(cls) -> None:
        cls._current_version.minor += 1
        cls._current_version.patch = 0
        cls._current_version.pre_release = None

    @classmethod
    def bump_patch(cls) -> None:
        cls._current_version.patch += 1

    @classmethod
    def set_pre_release(cls, tag: str) -> None:
        cls._current_version.pre_release = tag

    @classmethod
    def is_compatible(cls, version: Version) -> bool:
        """Check if version is within compatibility matrix."""
        if version.major != cls._current_version.major:
            return False
        if version.major < cls._matrix.minimum_major:
            return False
        if cls._matrix.maximum_major is not None and (
            version.major > cls._matrix.maximum_major
            or cls._current_version.major > cls._matrix.maximum_major
        ):
            return False
        return True

    @classmethod
    def check_dependencies(cls, deps: dict[str, str]) -> tuple[bool, list[str]]:
        """Check if required dependencies meet version requirements."""
        errors: list[str] = []
        for name, required_ver in deps.items():
            required = Version.parse(required_ver)
            if not cls.is_compatible(required):
                errors.append(
                    f"Incompatible {name}: {required} vs {cls._current_version}"
                )
        return len(errors) == 0, errors

    @classmethod
    def status(cls) -> dict[str, object]:
        """Return version status."""
        return {
            "current": str(cls._current_version),
            "major": cls._current_version.major,
            "minor": cls._current_version.minor,
            "patch": cls._current_version.patch,
            "pre_release": cls._current_version.pre_release,
            "compatible_range": f">={cls._matrix.minimum_major}.{cls._matrix.minimum_minor}.0",
        }
