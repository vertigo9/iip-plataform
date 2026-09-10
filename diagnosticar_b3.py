"""Diagnostico: isola qual parte da chamada a brapi.dev esta falhando.

Rode com:
    python diagnosticar_b3.py SEU_TOKEN_AQUI

Testa, em sequencia: PETR4 sozinho, MXRF11 sozinho, os dois juntos, e
token via query param em vez de header — para descobrir exatamente
onde esta o problema, em vez de adivinhar.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request


def tentar(descricao: str, url: str, headers: dict[str, str]) -> None:
    print(f"--- {descricao} ---")
    print(f"URL: {url}")
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        response = urllib.request.urlopen(request, timeout=20)
        body = response.read().decode("utf-8")
        print(f"status: {response.status}")
        print(f"corpo (primeiros 500 chars): {body[:500]}")
    except urllib.error.HTTPError as exc:
        corpo_erro = exc.read().decode("utf-8", errors="replace")
        print(f"ERRO HTTP {exc.code}: {corpo_erro[:500]}")
    except Exception as exc:
        print(f"ERRO: {exc}")
    print()


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python diagnosticar_b3.py SEU_TOKEN_AQUI")
        sys.exit(1)

    token = sys.argv[1]
    header_auth = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    tentar(
        "1) Só PETR4, token no header",
        "https://brapi.dev/api/quote/PETR4",
        header_auth,
    )
    tentar(
        "2) Só MXRF11, token no header",
        "https://brapi.dev/api/quote/MXRF11",
        header_auth,
    )
    tentar(
        "3) PETR4 + MXRF11 juntos, token no header",
        "https://brapi.dev/api/quote/PETR4,MXRF11",
        header_auth,
    )
    tentar(
        "4) Só MXRF11, token via query param (nao no header)",
        f"https://brapi.dev/api/quote/MXRF11?token={token}",
        {"Accept": "application/json"},
    )


if __name__ == "__main__":
    main()
