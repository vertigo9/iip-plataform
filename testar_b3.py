"""Teste manual: busca fundamentos/cotação reais via bolsai (B3).

Rode com:
    python testar_b3.py SUA_CHAVE_AQUI

Precisa de uma chave gratuita — crie conta (login Google) em
https://usebolsai.com e gere a chave no dashboard. Plano gratuito:
200 requisições/dia.

IMPORTANTE (descoberto ao vivo): ações e FIIs são endpoints
diferentes — /fundamentals/{ticker} para ações, /fiis/{ticker} para
FIIs. Chamar o endpoint errado devolve 404. Este script usa cada um
no lugar certo.

Faz chamada de rede real (api.usebolsai.com) — não é a B3 diretamente,
é um serviço de terceiros (ver docstring de iip.sources.b3_bolsai).
"""

from __future__ import annotations

import sys

from iip.sources.b3_bolsai import build_fii_target, build_target
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python testar_b3.py SUA_CHAVE_AQUI")
        sys.exit(1)

    api_key = sys.argv[1]
    harvester = BolsaiHTTPHarvester(api_key=api_key)

    print("--- Ação: PETR4 (endpoint /fundamentals) ---")
    stock_target = build_target("PETR4")
    print(f"URL: {stock_target.url}")
    try:
        resultado = harvester.fetch(stock_target)
        print(f"status HTTP: {resultado.status_code}")
        f = resultado.fundamentals
        print(
            f"{f.ticker}: preço={f.close_price} | P/L={f.pl} | "
            f"P/VP={f.pvp} | DY={f.dividend_yield}%"
        )
        if f.dividend_yield is None:
            print(
                "  aviso: DY veio None para esta ação — pode ser dado "
                "genuinamente ausente para PETR4 nesta data, ou um campo "
                "faltando; vale conferir de novo depois se persistir."
            )
    except Exception as exc:
        print(f"ERRO: {exc}")
    print()

    print("--- FII: MXRF11 (endpoint /fiis) ---")
    fii_target = build_fii_target("MXRF11")
    print(f"URL: {fii_target.url}")
    try:
        resultado = harvester.fetch_fii(fii_target)
        print(f"status HTTP: {resultado.status_code}")
        fii = resultado.fii
        print(
            f"{fii.ticker} ({fii.name}): preço={fii.close_price} | "
            f"P/VP={fii.pvp} | DY (TTM)={fii.dividend_yield_ttm}% | "
            f"segmento={fii.segment}"
        )
    except Exception as exc:
        print(f"ERRO: {exc}")


if __name__ == "__main__":
    main()
