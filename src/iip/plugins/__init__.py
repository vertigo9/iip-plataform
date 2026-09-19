"""Contrato de plugins do IIP (providers).

Um plugin é um módulo Python importável -- dentro ou fora deste repositório, desde
que esteja no PYTHONPATH -- que expõe:

    def iip_plugin_manifests() -> tuple[ProviderManifest, ...]: ...

Cada ``ProviderManifest`` (ver ``iip.providers.registry``) descreve um provider:
``name``, ``kind``, ``status``, ``asset_classes`` e ``source_roles``. Para o IIP
poder INSTANCIAR o provider (não só listá-lo), aponte ``implementation`` para a
classe, como ``"meu_pacote.meu_modulo.MeuProvider"``; o ``ProviderFactory`` a
importa e a instancia. Se o provider precisa de credencial, declare
``credential_setting`` (o campo de ``IIPSettings``, ex.: ``"bolsai_api_key"``) e
``credential_kwarg`` (o argumento do construtor); sem credencial configurada o
provider não é instanciado automaticamente -- nunca com um valor inventado. Um
manifesto com o nome de um provider embutido o SUBSTITUI (vale o último
registrado); os embutidos em si nunca são removidos.

Como ligar. Liste os módulos, separados por vírgula, em ``IIP_PLUGINS`` -- na
variável de ambiente ou no ``.env`` (a variável de ambiente tem precedência):

    IIP_PLUGINS=meu_pacote.plugin_a,meu_pacote.plugin_b

O CLI carrega os plugins a cada comando (``iip.providers.registry.load_plugins``).
Um plugin que não carrega -- erro de import, qualquer exceção ao importar ou ao
chamar ``iip_plugin_manifests()``, função ausente ou retorno que não seja uma
sequência de ``ProviderManifest`` -- vira uma falha registrada: nada dele é
registrado, os demais plugins e o comando seguem, o CLI avisa no stderr e o
``iip health`` mostra o check ``plugins`` como falho, com o motivo.

Segurança: isto executa código importável nomeado por uma variável. É aceitável
para uso local de um único usuário; não serve para um ambiente compartilhado,
que exigiria uma lista de plugins revisada/assinada.

Fora do escopo deste contrato (hoje): métodos de valuation, analisadores e perfis
de extração de PDF não são extensíveis por plugin -- vivem em tabelas do próprio
código (``portfolio_data/valuation_methods.py``, ``sources/fii_vacancia.py``).
Exemplo funcional: ``examples/meu_plugin_exemplo.py``.
"""
