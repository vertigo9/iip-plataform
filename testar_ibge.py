"""Teste manual: busca dados reais na API de Agregados do IBGE.

Rode com:
    python testar_ibge.py

Usa a tabela 7060 (IPCA, a partir de janeiro/2020 — sucessora da
tabela 1705, descontinuada). É o mesmo indicador que já buscamos do
BACEN (série 433): os dois deveriam bater, o que serve como conferência
cruzada entre as duas fontes. Faz chamada de rede real
(servicodados.ibge.gov.br).
"""

from __future__ import annotations

from iip.sources.ibge import build_target
from iip.sources.ibge_harvester import IbgeHTTPHarvester


def main() -> None:
    # Tabela 7060 = IPCA (vigente desde jan/2020). Sem variavel = pega
    # todas as variáveis da tabela (mais seguro do que adivinhar um ID).
    target = build_target(7060, periodos="-6", localidades="BR")
    print(f"URL: {target.url}\n")

    harvester = IbgeHTTPHarvester()
    try:
        resultado = harvester.fetch(target)
    except Exception as exc:
        print(f"ERRO: {exc}")
        return

    print(f"status HTTP: {resultado.status_code}")
    print(f"pontos recebidos: {len(resultado.points)}\n")

    for ponto in resultado.points[:20]:
        print(
            f"  {ponto.localidade_nome} | {ponto.periodo} | "
            f"{ponto.variavel_nome} = {ponto.value} {ponto.unidade}"
        )
    if len(resultado.points) > 20:
        print(f"  ... e mais {len(resultado.points) - 20} pontos")


if __name__ == "__main__":
    main()
