"""Production-safe runtime invocation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .certification import CertificationStatus, ProviderCertifier
from .factory import ProviderFactory


class RuntimeInvocationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeResult:
    provider: str
    method: str
    success: bool
    value: Any = None
    error: str | None = None


class ProviderRuntime:
    def __init__(
        self,
        factory: ProviderFactory | None = None,
        certifier: ProviderCertifier | None = None,
    ) -> None:
        self.factory = factory or ProviderFactory()
        self.certifier = certifier or ProviderCertifier(self.factory)

    def invoke(self, provider_name: str, method: str, *args, **kwargs) -> RuntimeResult:
        certification = self.certifier.certify(provider_name)
        if certification is None:
            return RuntimeResult(provider_name, method, False, error="unknown_provider")

        if certification.status != CertificationStatus.CERTIFIED:
            return RuntimeResult(
                provider_name, method, False, error=certification.status.value
            )

        if method not in certification.callable_surface:
            return RuntimeResult(
                provider_name, method, False, error="method_not_certified"
            )

        handle = self.factory.create(provider_name)
        if handle is None or handle.provider is None:
            return RuntimeResult(
                provider_name, method, False, error="implementation_unavailable"
            )

        try:
            value = getattr(handle.provider, method)(*args, **kwargs)
            return RuntimeResult(provider_name, method, True, value=value)
        # isola falha do metodo do provider num RuntimeResult, nao deixa propagar
        except Exception as exc:  # noqa: BLE001
            return RuntimeResult(
                provider_name,
                method,
                False,
                error=f"{type(exc).__name__}:{exc}",
            )
