"""Exemplo de plugin externo para o IIP.

Qualquer módulo Python importável vira um plugin do IIP se expuser uma
função ``iip_plugin_manifests()`` que devolve uma tupla de
``ProviderManifest``. Este arquivo é só um exemplo — pode estar em
qualquer lugar do seu sistema, dentro ou fora deste repositório, desde
que esteja no PYTHONPATH quando o IIP rodar.
"""

from __future__ import annotations

from iip.providers.registry import ProviderKind, ProviderManifest, ProviderStatus


def iip_plugin_manifests() -> tuple[ProviderManifest, ...]:
    return (
        ProviderManifest(
            name="meu_provider_exemplo",
            kind=ProviderKind.MACRO,
            status=ProviderStatus.READY,
            asset_classes=("fund", "equity"),
            source_roles=("enrichment",),
            implementation=None,  # aponte para sua classe/harvester real aqui
            notes="Plugin de exemplo, registrado via IIP_PLUGINS.",
        ),
    )
