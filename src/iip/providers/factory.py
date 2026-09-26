"""Provider factory with compatibility for existing implementations."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from inspect import isclass

from iip.config import IIPSettings, get_settings

from .registry import ProviderManifest, ProviderStatus, manifest_map


@dataclass(frozen=True)
class ProviderHandle:
    manifest: ProviderManifest
    provider: object | None


class ProviderFactory:
    def __init__(self, manifests=None, settings: IIPSettings | None = None) -> None:
        self.manifests = {
            item.name: item for item in (manifests or manifest_map().values())
        }
        self._settings = settings or get_settings()

    def manifest(self, name: str) -> ProviderManifest | None:
        return self.manifests.get(name.strip().lower())

    @staticmethod
    def _instantiate_implementation(
        implementation: str, credential_kwargs: dict[str, str] | None = None
    ) -> object:
        module_name, symbol_name = implementation.rsplit(".", 1)
        module = importlib.import_module(module_name)
        symbol = getattr(module, symbol_name)

        if isclass(symbol):
            return symbol(**(credential_kwargs or {}))

        return symbol

    def _resolve_credential_kwargs(
        self, manifest: ProviderManifest
    ) -> dict[str, str] | None:
        """Look up manifest.credential_setting on IIPSettings and, if a
        value is actually set, return the {credential_kwarg: value}
        dict the implementation's constructor expects. Returns None if
        the manifest declares no credential (nothing to inject) or the
        setting exists but is empty (caller should treat this the same
        as "not configured yet" — never invent a placeholder value).
        """
        if not manifest.credential_setting or not manifest.credential_kwarg:
            return None

        raw_value = getattr(self._settings, manifest.credential_setting, None)
        if raw_value is None:
            return None

        # SecretStr and friends — unwrap to the actual string the
        # constructor needs; plain strings pass through unchanged.
        value = (
            raw_value.get_secret_value()
            if hasattr(raw_value, "get_secret_value")
            else raw_value
        )
        if not value:
            return None

        return {manifest.credential_kwarg: value}

    def create(self, name: str) -> ProviderHandle | None:
        manifest = self.manifest(name)
        if manifest is None:
            return None

        if not manifest.implementation:
            return ProviderHandle(manifest, None)

        if manifest.status == ProviderStatus.PENDING:
            return ProviderHandle(manifest, None)

        if manifest.status == ProviderStatus.PARTIAL:
            credential_kwargs = self._resolve_credential_kwargs(manifest)
            if credential_kwargs is None:
                # Either this PARTIAL provider needs something other than
                # a credential (e.g. mziq's per-company config), or the
                # credential just isn't set — either way, nothing safe to
                # instantiate automatically.
                return ProviderHandle(manifest, None)
            return ProviderHandle(
                manifest,
                self._instantiate_implementation(
                    manifest.implementation, credential_kwargs
                ),
            )

        return ProviderHandle(
            manifest,
            self._instantiate_implementation(manifest.implementation),
        )
