"""Teste manual: busca documentos reais de RI via MZIQ (genérico).

Rode com:
    python testar_mziq.py

Usa o company_id e as categorias do ABC Brasil (ABCB4), confirmados ao
vivo nesta sessão. Para outra empresa que também use MZIQ, troque
COMPANY_ID e CATEGORIES pelos valores dela (descobertos via
reconhecer_mziq.py + reconhecer_mziq_2.py contra a página de RI dela).

Faz chamada de rede real (apicatalog.mziq.com) — não precisa de
autenticação, confirmado ao vivo.
"""

from __future__ import annotations

from iip.sources.mziq import build_documents_target, build_years_target
from iip.sources.mziq_harvester import MziqHTTPHarvester

COMPANY_ID = "6298ef6f-2b75-43f8-b2ab-99e3fe33e809"  # ABC Brasil (ABCB4)
CATEGORIES = (
    "central-resultados-earnings-release",
    "central-resultados-dfp",
    "central-resultados-itr",
    "central-resultados-df-prudencial",
    "central-resultados-df",
    "central-resultados-apresentacao",
    "central-resultados-fact-sheet",
    "central-resultados-teleconferencia-slides",
    "central-resultados-teleconferencia",
    "central-resultados-transcricao",
    "central-resultados-series-historicas",
)


def main() -> None:
    harvester = MziqHTTPHarvester()

    years_target = build_years_target(COMPANY_ID, CATEGORIES)
    print(f"URL (anos): {years_target.url}")
    anos = harvester.fetch_years(years_target)
    print(f"Anos disponíveis: {anos}\n")

    if not anos:
        print("Nenhum ano retornado — algo mudou na API, investigar.")
        return

    ano_mais_recente = anos[0]
    docs_target = build_documents_target(COMPANY_ID, ano_mais_recente, CATEGORIES)
    print(f"URL (documentos {ano_mais_recente}): {docs_target.url}")
    documentos = harvester.fetch_documents(docs_target)

    print(f"\n{len(documentos)} documento(s) em {ano_mais_recente}:")
    for doc in documentos:
        print(f"  [{doc.category}] {doc.file_title} ({doc.file_date}) -> {doc.url}")


if __name__ == "__main__":
    main()
