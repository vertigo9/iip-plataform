"""Demonstração do sistema de plugins: descoberta via variável de ambiente.

Rode com (do jeito que o plugin de exemplo pede a variável IIP_PLUGINS):

    $env:IIP_PLUGINS = "examples.meu_plugin_exemplo"
    python testar_plugins.py

Não faz chamada de rede nenhuma — é só demonstrar o mecanismo de
registro/descoberta.
"""

from __future__ import annotations

import os

from iip.providers.registry import discover_plugins, manifest_map


def main() -> None:
    print(f"IIP_PLUGINS = {os.environ.get('IIP_PLUGINS', '(não definida)')}\n")

    print("Providers embutidos que já vêm prontos (READY):")
    for manifest in manifest_map().values():
        if manifest.status.value == "ready":
            print(f"  - {manifest.name} ({manifest.kind.value})")

    print("\nDescobrindo plugins externos...")
    descobertos = discover_plugins()

    if not descobertos:
        print(
            "Nenhum plugin descoberto. Defina IIP_PLUGINS antes de rodar "
            "este script (veja o cabeçalho do arquivo)."
        )
        return

    print(f"\n{len(descobertos)} manifesto(s) de plugin registrado(s):")
    for manifest in descobertos:
        print(f"  - {manifest.name} ({manifest.kind.value}) — {manifest.notes}")

    print("\nAgora aparecem também no mapa geral de providers:")
    todos = manifest_map()
    for manifest in descobertos:
        assert manifest.name in todos  # confirma que entrou no registro geral
        print(f"  - {manifest.name}: {todos[manifest.name].status.value}")


if __name__ == "__main__":
    main()
