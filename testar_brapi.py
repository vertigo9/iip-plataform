"""Teste manual: busca cotações reais via brapi.dev (ação + FII + BDR).

Rode com:
    python testar_brapi.py SEU_TOKEN_AQUI

Precisa de um token da brapi.dev (mesmo que você já usou antes — se
tiver trocado, gera um novo em https://brapi.dev/dashboard).

IMPORTANTE: o plano gratuito permite só 1 ativo por requisição — por
isso uma chamada por ticker, via fetch_many().

Faz chamada de rede real (brapi.dev) — não é a B3 diretamente. Mantido
ao lado do bolsai (testar_b3.py): cada um cobre uma lacuna que o outro
não cobre — bolsai não cobre BDR, brapi.dev cobre.
"""

from __future__ import annotations

import sys

from iip.sources.b3_brapi import build_target
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python testar_brapi.py SEU_TOKEN_AQUI")
        sys.exit(1)

    token = sys.argv[1]
    # Uma ação, um FII, e um BDR — cobre os três casos que essa fonte suporta.
    tickers = ("PETR4", "MXRF11", "AAPL34")

    targets = tuple(build_target((ticker,)) for ticker in tickers)

    harvester = BrapiHTTPHarvester(token=token)
    resultados = harvester.fetch_many(targets)

    for resultado in resultados:
        print(f"URL: {resultado.target.url}")
        print(f"status HTTP: {resultado.status_code}")
        for quote in resultado.quotes:
            print(
                f"  {quote.symbol} ({quote.short_name}) | "
                f"{quote.regular_market_price} {quote.currency} | "
                f"variação: {quote.regular_market_change_percent}%"
            )
        print()


if __name__ == "__main__":
    main()
