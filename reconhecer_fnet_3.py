"""Reconhecimento FNET, parte 3 — o script clica sozinho nos filtros.

Abre a página, clica em "EXIBIR FILTROS", seleciona "Fundo Imobiliário"
no tipo de fundo, clica em "Filtrar", e captura a resposta da API
diretamente pelo Playwright (sem precisar mexer no DevTools).

Rode com:
    python reconhecer_fnet_3.py

Gera fnet_reconhecimento/resposta_filtrada.json com o resultado real.
Se o clique automático em algum passo falhar, o script avisa qual foi
e ainda assim deixa o navegador aberto por 30 segundos para você poder
terminar manualmente e ver o que acontece.
"""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT_DIR = Path("fnet_reconhecimento")
SEARCH_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosCVM"
API_URL_FRAGMENT = "pesquisarGerenciadorDocumentosDados"


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
    capturas: list[dict] = []

    def on_response(response):
        if API_URL_FRAGMENT in response.url:
            try:
                body = response.json()
            except Exception:
                body = response.text()
            capturas.append({"url": response.url, "status": response.status, "body": body})
            n = len(body.get("data", [])) if isinstance(body, dict) else "?"
            print(f"  capturado: {response.url[:100]}... -> {n} registros")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.on("response", on_response)

        print(f"Abrindo {SEARCH_URL} ...")
        page.goto(SEARCH_URL, timeout=60000)
        page.wait_for_timeout(4000)

        try:
            print("Clicando em 'EXIBIR FILTROS'...")
            page.click("#showFiltros", timeout=10000)
            page.wait_for_timeout(1500)

            print("Selecionando 'Fundo Imobiliário' em Tipo de Fundo...")
            page.select_option("#tipoFundo", label="Fundo Imobiliário")
            page.wait_for_timeout(1000)

            print("Clicando em 'Filtrar'...")
            page.click("#filtrar", timeout=10000)
            page.wait_for_timeout(5000)

        except Exception as exc:
            print(f"\nUm dos passos automáticos falhou: {exc}")
            print(
                "O navegador vai ficar aberto por 30 segundos — tenta fazer "
                "esse passo manualmente (clicar em EXIBIR FILTROS, escolher "
                "Fundo Imobiliário, clicar em Filtrar) que o script continua "
                "capturando as respostas em segundo plano."
            )
            page.wait_for_timeout(30000)

        (OUTPUT_DIR / "resposta_filtrada.json").write_text(
            json.dumps(capturas, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n{len(capturas)} resposta(s) da API capturada(s) e salvas.")

        browser.close()

    print(f"Confira '{OUTPUT_DIR}/resposta_filtrada.json' e me manda o conteúdo.")


if __name__ == "__main__":
    main()
