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
                ProviderStatus.PARTIAL,
                ("fund",),
                ("regulatory",),
                implementation="iip.sources.cvm_fii_harvester.CvmFiiHTTPHarvester",
                notes=(
                    "FII Informe Mensal Estruturado via CVM's open-data "
                    "portal (dados.cvm.gov.br) — no auth, no JS, no "
                    "Cloudflare, unlike FNET's own search UI (audited and "
                    "found to require a real filter + resist automation). "
                    "Keyed by CNPJ, so it covers financial data for "
                    "effectively all FII managers (BTG, Sparta, Rio Bravo, "
                    "Kinea, etc.) in one provider. NOT multi-asset despite "
                    "asset_classes on the generic ProviderManifest shape: "
                    "PARTIAL, not READY, because this implementation is "
                    "FII-only — see the separate 'cvm_fiagro' entry for "
                    "FIAGRO. FIDC has its own separate CVM open-data "
                    "dataset with a different, more complex column "
                    "structure (fidc-doc-inf_mensal, tab_I/tab_X tables) — "
                    "not yet implemented. Equities/BDRs use an entirely "
                    "different CVM regime (Formulário de Referência, "
                    "DFP/ITR for Companhias Abertas, not 'informe mensal'). "
                    "ICVM 555 fixed-income funds have their own 'perfil "
                    "mensal'/'informe diário' datasets, also different. "
                    "Each would need its own target-builder/parser pair, "
                    "the same as this one."
                ),
            ),
            ProviderManifest(
                "cvm_fiagro",
                ProviderKind.REGULATORY,
                ProviderStatus.READY,
                ("fund",),
                ("regulatory",),
                implementation="iip.sources.cvm_fiagro_harvester.CvmFiagroHTTPHarvester",
                notes=(
                    "FIAGRO Informe Mensal via CVM's open-data portal — "
                    "same channel as 'cvm' (FII) but a genuinely different "
                    "dataset: published monthly (not yearly), one combined "
                    "133-column file per competência (not FII's separate "
                    "geral/ativo_passivo/complemento files) plus a small "
                    "subclass-level file. Confirmed live against a real "
                    "downloaded file (inf_mensal_fiagro_202508.zip), not "
                    "assumed from FII's structure."
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
                ProviderStatus.PARTIAL,
                ("equity",),
                ("institutional_primary",),
                implementation="iip.sources.mziq_harvester.MziqHTTPHarvester",
                notes=(
                    "Generic MZIQ (MZ Group) investor-relations document "
                    "catalog — shared infrastructure confirmed live across "
                    "many Brazilian public companies (not just one), same "
                    "general concept already used for a single company by "
                    "iip.harvest.patria. PARTIAL, not READY: the harvester "
                    "itself instantiates with no arguments, but every call "
                    "needs a company_id and category_internal_names that "
                    "are specific to each company's IR site — there is no "
                    "single registry of these yet. Discover them per "
                    "company the same way ABC Brasil's (ABCB4) were found: "
                    "run reconhecer_mziq.py against the company's "
                    "'Central de Resultados'-style page, then "
                    "reconhecer_mziq_2.py to capture the response body. "
                    "Companies not on the MZIQ platform need a different "
                    "provider entirely — this only covers MZIQ-hosted IR "
                    "sites."
                ),
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
                "cvm_renda_fixa",
                ProviderKind.REGULATORY,
                ProviderStatus.READY,
                ("fixed_income",),
                ("regulatory",),
                implementation=(
                    "iip.sources.cvm_renda_fixa_harvester.CvmRendaFixaHTTPHarvester"
                ),
                notes=(
                    "ICVM 555 funds via CVM's open-data portal — two "
                    "datasets, both confirmed live against real downloaded "
                    "files (inf_diario_fi_202608.zip, "
                    "perfil_mensal_fi_202608.csv). Informe Diário: dense "
                    "daily NAV time series (VL_QUOTA, PL, "
                    "captações/resgates) — 533k rows for one month across "
                    "thousands of funds, exactly the historical-series data "
                    "the quantitative/timing module needs. Perfil Mensal: "
                    "107-column risk/shareholder-composition profile, kept "
                    "as raw strings in 'valores' rather than force-parsed "
                    "as float (unlike FII/FIAGRO's numeric-only dicts) "
                    "since this file genuinely mixes numbers, free text, "
                    "and empty cells. Note: Perfil Mensal's URL is a plain "
                    "CSV, not a ZIP like every other CVM dataset used in "
                    "this project — confirmed live, not assumed."
                ),
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
