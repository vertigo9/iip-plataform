"""Provider validation workflow."""

from __future__ import annotations

from dataclasses import dataclass

from .operations import ProviderOperations


@dataclass(frozen=True)
class ProviderValidation:
    name: str
    registered: bool
    implemented: bool
    ready: bool
    action: str


class ProviderValidator:
    def __init__(self, operations: ProviderOperations | None = None) -> None:
        self.operations = operations or ProviderOperations()

    def validate(self, provider_name: str) -> ProviderValidation:
        diagnostic = self.operations.diagnostic(provider_name)
        if diagnostic is None:
            return ProviderValidation(
                provider_name, False, False, False, "register_provider"
            )
        if not diagnostic.implemented:
            return ProviderValidation(
                provider_name, True, False, False, "implement_provider"
            )
        if not diagnostic.usable_for_production:
            return ProviderValidation(
                provider_name, True, True, False, "promote_after_validation"
            )
        return ProviderValidation(provider_name, True, True, True, "ready")

    def validate_all(self):
        return tuple(
            sorted(
                (self.validate(name) for name in self.operations.factory.manifests),
                key=lambda item: item.name,
            )
        )
