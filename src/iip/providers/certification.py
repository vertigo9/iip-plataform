"""Provider certification and runtime safety layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .factory import ProviderFactory


class CertificationStatus(StrEnum):
    CERTIFIED = "certified"
    INCOMPLETE = "incomplete"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ProviderCertification:
    provider: str
    status: CertificationStatus
    callable_surface: tuple[str, ...]
    notes: tuple[str, ...] = ()


class ProviderCertifier:
    DEFAULT_SURFACE = (
        "supports",
        "discover",
        "collect",
        "harvest",
        "fetch",
    )

    def __init__(self, factory: ProviderFactory | None = None) -> None:
        self.factory = factory or ProviderFactory()

    def certify(self, name: str) -> ProviderCertification | None:
        manifest = self.factory.manifest(name)
        if manifest is None:
            return None

        # A registered provider whose concrete implementation is pending is
        # not blocked by policy; it is simply incomplete.
        if not manifest.implementation:
            return ProviderCertification(
                name,
                CertificationStatus.INCOMPLETE,
                (),
                ("no_concrete_implementation",),
            )

        try:
            handle = self.factory.create(name)
        except Exception as exc:
            return ProviderCertification(
                name,
                CertificationStatus.INCOMPLETE,
                (),
                (f"factory_error:{type(exc).__name__}",),
            )

        if handle is None or handle.provider is None:
            return ProviderCertification(
                name,
                CertificationStatus.INCOMPLETE,
                (),
                ("implementation_unavailable",),
            )

        surface = tuple(
            method
            for method in self.DEFAULT_SURFACE
            if callable(getattr(handle.provider, method, None))
        )

        if not surface:
            return ProviderCertification(
                name,
                CertificationStatus.INCOMPLETE,
                (),
                ("no_supported_runtime_method_detected",),
            )

        return ProviderCertification(
            name,
            CertificationStatus.CERTIFIED,
            surface,
            ("runtime_surface_detected",),
        )
