"""Operational provider manifest registry.

Extended in this session to support runtime-registered providers, on
top of the fixed built-in list already here — the built-ins never
disappear, runtime registration only adds to (or, if the same name is
reused, overrides) them. See ``register_manifest`` and
``discover_plugins`` below.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from enum import StrEnum

from iip.logging import get_logger

logger = get_logger(__name__)


class ProviderKind(StrEnum):
    INSTITUTIONAL = "institutional"
    REGULATORY = "regulatory"
    MARKET = "market"
    ISSUER = "issuer"
    MACRO = "macro"  # reference/macroeconomic series, not per-asset (BACEN, IBGE)


class ProviderStatus(StrEnum):
    REGISTERED = "registered"
    READY = "ready"
    PARTIAL = "partial"
    PENDING = "pending"


@dataclass(frozen=True)
class ProviderManifest:
    name: str
    kind: ProviderKind
    status: ProviderStatus
    asset_classes: tuple[str, ...]
    source_roles: tuple[str, ...]
    implementation: str | None = None
    notes: str | None = None


FUND_MANAGERS = (
    "xp_asset",
    "patria",
    "sparta",
    "capitania",
    "valora",
    "btg",
    "manati",
    "trx",
    "araujo_fontes",
    "hedge",
    "rio_bravo",
    "kinea",
)

TRANSVERSAL_PROVIDERS = (
    "cvm",
    "fnet",
    "b3",
    "ri_company",
    "sec",
    "issuer",
    "market_data",
)


def default_provider_manifests() -> tuple[ProviderManifest, ...]:
    result = []
    for name in FUND_MANAGERS:
        result.append(
            ProviderManifest(
                name=name,
                kind=ProviderKind.INSTITUTIONAL,
                status=ProviderStatus.READY
                if name in {"xp_asset", "patria"}
                else ProviderStatus.PENDING,
                asset_classes=("fund",),
                source_roles=("institutional_primary",),
                implementation=(
                    "iip.sources.xp_asset.XPAssetProvider"
                    if name == "xp_asset"
                    else "iip.harvest.patria"
                    if name == "patria"
                    else None
                ),
            )
        )
    result.extend(
        [
            ProviderManifest(
                "cvm",
                ProviderKind.REGULATORY,
                ProviderStatus.READY,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("regulatory",),
                implementation="iip.sources.cvm_fii_harvester.CvmFiiHTTPHarvester",
                notes=(
                    "FII Informe Mensal Estruturado via CVM's open-data "
                    "portal (dados.cvm.gov.br) — no auth, no JS, no "
                    "Cloudflare, unlike FNET's own search UI (audited and "
                    "found to require a real filter + resist automation). "
                    "Since this is keyed by CNPJ, not per-manager scraping, "
                    "it covers financial data for effectively all FII "
                    "managers (BTG, Sparta, Rio Bravo, Kinea, etc.) in one "
                    "provider — reducing the need for bespoke per-manager "
                    "harvesters to those wanting non-financial documents "
                    "(e.g. investor presentations) beyond what CVM's "
                    "structured report covers."
                ),
            ),
            ProviderManifest(
                "fnet",
                ProviderKind.REGULATORY,
                ProviderStatus.REGISTERED,
                ("fund",),
                ("regulatory",),
            ),
            ProviderManifest(
                "b3",
                ProviderKind.MARKET,
                ProviderStatus.PARTIAL,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("market_validation",),
                implementation="iip.sources.b3_bolsai_harvester.BolsaiHTTPHarvester",
                notes=(
                    "Implemented via bolsai (third-party wrapper, not B3 "
                    "directly — see module docstring). PARTIAL, not READY: "
                    "the harvester requires an api_key constructor argument "
                    "with no default, so ProviderFactory's zero-arg "
                    "instantiation fails today. Needs credential-injection "
                    "support in ProviderFactory before this can be READY."
                ),
            ),
            ProviderManifest(
                "ri_company",
                ProviderKind.INSTITUTIONAL,
                ProviderStatus.PENDING,
                ("equity",),
                ("institutional_primary",),
            ),
            ProviderManifest(
                "sec",
                ProviderKind.REGULATORY,
                ProviderStatus.REGISTERED,
                ("adr",),
                ("regulatory",),
            ),
            ProviderManifest(
                "issuer",
                ProviderKind.ISSUER,
                ProviderStatus.PENDING,
                ("etf", "bdr", "adr"),
                ("institutional_primary",),
            ),
            ProviderManifest(
                "market_data",
                ProviderKind.MARKET,
                ProviderStatus.REGISTERED,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("enrichment",),
            ),
            ProviderManifest(
                "bacen",
                ProviderKind.MACRO,
                ProviderStatus.READY,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("enrichment",),
                implementation="iip.sources.bacen_harvester.BacenHTTPHarvester",
                notes="SELIC/CDI/IPCA via BACEN's public SGS API. No credentials needed.",
            ),
            ProviderManifest(
                "ibge",
                ProviderKind.MACRO,
                ProviderStatus.READY,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("enrichment",),
                implementation="iip.sources.ibge_harvester.IbgeHTTPHarvester",
                notes=(
                    "Generic IBGE Agregados/SIDRA access. No credentials "
                    "needed. No specific table/variable is hardcoded — "
                    "callers must supply those explicitly."
                ),
            ),
            ProviderManifest(
                "receita_federal",
                ProviderKind.REGULATORY,
                ProviderStatus.READY,
                ("fund", "equity", "etf", "bdr", "adr", "fixed_income", "other"),
                ("regulatory",),
                implementation="iip.sources.receita_federal_harvester.ReceitaFederalHTTPHarvester",
                notes="CNPJ lookup via BrasilAPI (third-party, not Receita Federal directly). No credentials needed.",
            ),
        ]
    )
    return tuple(result)


_runtime_manifests: dict[str, ProviderManifest] = {}


def register_manifest(manifest: ProviderManifest) -> None:
    """Register a provider manifest at runtime.

    Adds to the built-in manifests from ``default_provider_manifests()``
    — never removes or mutates them. Registering a name that matches a
    built-in overrides it for lookups via ``manifest_map()`` (last
    registration wins), which is how a plugin can supersede a
    ``PENDING``/``PARTIAL`` built-in once a real implementation exists.
    """
    _runtime_manifests[manifest.name] = manifest
    logger.info("provider_manifest_registered", provider=manifest.name)


def unregister_manifest(name: str) -> None:
    """Remove a runtime-registered manifest. Built-ins are never
    affected — this cannot remove a manifest from
    ``default_provider_manifests()``."""
    _runtime_manifests.pop(name, None)


def clear_runtime_manifests() -> None:
    """Remove all runtime-registered manifests (built-ins unaffected).
    Mainly useful for test isolation between test modules that call
    ``register_manifest``."""
    _runtime_manifests.clear()


def manifest_map() -> dict[str, ProviderManifest]:
    merged = {item.name: item for item in default_provider_manifests()}
    merged.update(_runtime_manifests)
    return merged


def discover_plugins(env_var: str = "IIP_PLUGINS") -> tuple[ProviderManifest, ...]:
    """Import plugin modules named in ``env_var`` (comma-separated
    dotted module paths) and register any manifests they expose.

    A plugin module must define ``iip_plugin_manifests() -> tuple[ProviderManifest, ...]``;
    modules without that function are skipped, not errored. A module
    that fails to import is logged and skipped — one broken plugin
    must not prevent the others (or the application) from starting.

    Security note: this executes arbitrary importable code named by an
    environment variable. That is an accepted tradeoff for local,
    single-user use — it is not appropriate for a shared or
    multi-tenant deployment, which would need a vetted/signed plugin
    list instead of "anything importable in this environment".
    """
    raw = os.environ.get(env_var, "")
    module_names = tuple(name.strip() for name in raw.split(",") if name.strip())

    discovered: list[ProviderManifest] = []
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            logger.error("plugin_import_failed", module=module_name, error=str(exc))
            continue

        factory_fn = getattr(module, "iip_plugin_manifests", None)
        if factory_fn is None:
            logger.error("plugin_missing_manifest_function", module=module_name)
            continue

        for manifest in factory_fn():
            register_manifest(manifest)
            discovered.append(manifest)

    return tuple(discovered)
