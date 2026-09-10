"""Teste manual: consulta um CNPJ real na BrasilAPI (Receita Federal).

Rode com:
    python testar_receita_federal.py

Sem chave/token necessário. Usa o CNPJ do Google Brasil Internet Ltda.
como exemplo (é o mesmo usado na documentação pública da BrasilAPI).
Pode passar outro CNPJ como argumento:
    python testar_receita_federal.py 00000000000191

Faz chamada de rede real (brasilapi.com.br) — não é a Receita Federal
diretamente, é um agregador de terceiros (ver docstring de
iip.sources.receita_federal).
"""

from __future__ import annotations

import sys

from iip.sources.receita_federal import build_target
from iip.sources.receita_federal_harvester import ReceitaFederalHTTPHarvester


def main() -> None:
    cnpj = sys.argv[1] if len(sys.argv) > 1 else "06990590000123"  # Google Brasil

    target = build_target(cnpj)
    print(f"URL: {target.url}\n")

    harvester = ReceitaFederalHTTPHarvester()
    try:
        resultado = harvester.fetch(target)
    except Exception as exc:
        print(f"ERRO: {exc}")
        return

    print(f"status HTTP: {resultado.status_code}")
    r = resultado.record
    print(f"Razão social: {r.razao_social}")
    print(f"Nome fantasia: {r.nome_fantasia}")
    print(f"Situação cadastral: {r.situacao_cadastral}")
    print(f"Natureza jurídica: {r.natureza_juridica}")
    print(f"CNAE principal: {r.cnae_fiscal} - {r.cnae_fiscal_descricao}")
    print(f"Município/UF: {r.municipio}/{r.uf}")
    print(f"Capital social: {r.capital_social}")
    print(f"CNAEs secundários: {len(r.cnaes_secundarios)}")


if __name__ == "__main__":
    main()
