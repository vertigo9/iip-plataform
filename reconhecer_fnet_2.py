"""Reconhecimento FNET, parte 2 — chama a API de dentro da página.

A tentativa anterior mostrou que chamar a URL da API diretamente (fora
do contexto da página) devolve vazio — o site distingue navegação
direta de chamada interna (comum em sites com Cloudflare). Este script
carrega a página de busca de verdade e dispara a mesma chamada via
fetch() DENTRO do navegador, replicando exatamente o que o site faz
sozinho.

Rode com:
    python reconhecer_fnet_2.py

Gera fnet_reconhecimento/resposta_api_real.json com uma amostra real
de documentos — é isso que vou usar para desenhar o parser certo, sem
adivinhar nome de campo.
"""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT_DIR = Path("fnet_reconhecimento")
SEARCH_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosCVM"
API_PATH = (
    "/fnet/publico/pesquisarGerenciadorDocumentosDados"
    "?d=1&s=0&l=50&o%5B0%5D%5BdataReferencia%5D=desc"
    "&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0&isSession=true"
)


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright não está instalado. Rode:\n"
            "  pip install playwright --break-system-packages\n"
            "  python -m playwright install chromium"
        )
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print(f"Abrindo {SEARCH_URL} (deixando a página carregar de verdade)...")
        page.goto(SEARCH_URL, timeout=60000)
        page.wait_for_timeout(5000)  # tempo pro Cloudflare/JS da pagina resolver

        print("Disparando a chamada de dentro da página via fetch()...")
        resultado = page.evaluate(
            """
            async (path) => {
                const resp = await fetch(path, {
                    method: 'GET',
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const status = resp.status;
                let body;
                try {
                    body = await resp.json();
                } catch (e) {
                    body = await resp.text();
                }
                return { status, body };
            }
            """,
            API_PATH,
        )

        print(f"Status da chamada interna: {resultado['status']}")
        registros = 0
        if isinstance(resultado["body"], dict):
            registros = len(resultado["body"].get("data", []))
        print(f"Registros recebidos: {registros}")

        (OUTPUT_DIR / "resposta_api_real.json").write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        browser.close()

    print(f"\nSalvei em '{OUTPUT_DIR}/resposta_api_real.json'. Me manda o conteúdo desse arquivo.")


if __name__ == "__main__":
    main()
