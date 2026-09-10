"""Teste manual: busca SELIC, CDI e IPCA de verdade na API do BACEN.

Rode com:
    python testar_bacen.py

Faz chamadas de rede reais (api.bcb.gov.br) — não roda em CI/sandbox
sem acesso à internet, só na sua máquina.
"""

from __future__ import annotations

from datetime import date, timedelta

from iip.sources.bacen import CDI, IPCA, SELIC, build_target
from iip.sources.bacen_harvester import BacenHTTPHarvester


def main() -> None:
    hoje = date.today()
    inicio = hoje - timedelta(days=60)
    harvester = BacenHTTPHarvester()

    series = {"SELIC": SELIC, "CDI": CDI, "IPCA": IPCA}

    for nome, codigo in series.items():
        print(f"\n=== {nome} (série {codigo}) — últimos 60 dias ===")
        target = build_target(codigo, inicio, hoje)
        print(f"URL: {target.url}")
        try:
            resultado = harvester.fetch(target)
        except Exception as exc:
            print(f"  -> ERRO: {exc}")
            continue
        print(f"  -> status HTTP: {resultado.status_code}")
        print(f"  -> pontos recebidos: {len(resultado.points)}")
        if resultado.points:
            ultimo = resultado.points[-1]
            print(f"  -> último valor: {ultimo.date.isoformat()} = {ultimo.value}")


if __name__ == "__main__":
    main()
