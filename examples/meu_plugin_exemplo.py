"""Exemplo de plugin externo para o IIP.

Qualquer módulo Python importável vira um plugin do IIP se expuser uma
função ``iip_plugin_manifests()`` que devolve uma tupla de
``ProviderManifest``. Este arquivo é só um exemplo — pode estar em
qualquer lugar do seu sistema, dentro ou fora deste repositório, desde
que esteja no PYTHONPATH quando o IIP rodar. O contrato completo está em
``iip.plugins``.

Para ligar (o CLI carrega a cada comando):

    $env:IIP_PLUGINS = "examples.meu_plugin_exemplo"
    iip health        # a linha "plugins" mostra que este módulo carregou
"""

from __future__ import annotations

from iip.providers.registry import ProviderKind, ProviderManifest, ProviderStatus


class MeuProviderExemplo:
    """Provider mínimo: o ``ProviderFactory`` o instancia a partir do
    ``implementation`` do manifesto abaixo."""

    def collect(self) -> str:
        return "dado de exemplo"


def iip_plugin_manifests() -> tuple[ProviderManifest, ...]:
    return (
        ProviderManifest(
            name="meu_provider_exemplo",
            kind=ProviderKind.MACRO,
            status=ProviderStatus.READY,
            asset_classes=("fund", "equity"),
            source_roles=("enrichment",),
            implementation="examples.meu_plugin_exemplo.MeuProviderExemplo",
            notes="Plugin de exemplo, registrado via IIP_PLUGINS.",
        ),
    )
