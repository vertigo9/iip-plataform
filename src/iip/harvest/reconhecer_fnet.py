"""Reconhecimento do FNET via Playwright — NÃO é o harvester final.

Objetivo: abrir a página pública de busca do FNET, capturar todas as
chamadas de rede que a página faz (pode revelar uma API JSON por trás
do formulário), listar os campos de busca disponíveis, e salvar tudo
em disco para eu poder desenhar o harvester de verdade com base no que
a página realmente faz — em vez de adivinhar seletores.

Não precisa de login. Roda em modo visível (headed) de propósito, para
você acompanhar o que está acontecendo.

Instalação (só na primeira vez):
    pip install playwright --break-system-packages
    python -m playwright install chromium

Rode com:
    python reconhecer_fnet.py

Gera uma pasta `fnet_reconhecimento/` com:
    - pagina_inicial.png       (screenshot da busca antes de preencher)
    - pagina_inicial.html      (HTML completo da página)
    - campos_formulario.json   (todo input/select/button encontrado)
    - rede_pagina_inicial.json (toda chamada de rede no carregamento)
    - pagina_apos_busca.png    (screenshot depois de tentar buscar "BTLG11")
    - rede_apos_busca.json     (chamadas de rede durante a busca)
"""

from __future__ import annotations

import json
from pathlib import Path

SEARCH_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosCVM"
OUTPUT_DIR = Path("fnet_reconhecimento")
TERMO_TESTE = "BTLG11"


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
    network_log_inicial: list[dict] = []
    network_log_busca: list[dict] = []
    current_log = network_log_inicial

    def on_request(request):
        current_log.append(
            {
                "tipo": "request",
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
            }
        )

    def on_response(response):
        try:
            content_type = response.headers.get("content-type", "")
        except Exception:
            content_type = ""
        current_log.append(
            {
                "tipo": "response",
                "status": response.status,
                "url": response.url,
                "content_type": content_type,
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.on("request", on_request)
        page.on("response", on_response)

        print(f"Abrindo {SEARCH_URL} ...")
        page.goto(SEARCH_URL, timeout=60000)
        page.wait_for_timeout(4000)  # dá tempo pra qualquer JS lazy carregar

        print("Salvando screenshot e HTML da página inicial...")
        page.screenshot(path=str(OUTPUT_DIR / "pagina_inicial.png"), full_page=True)
        (OUTPUT_DIR / "pagina_inicial.html").write_text(page.content(), encoding="utf-8")

        print("Listando campos do formulário...")
        campos = page.evaluate(
            """
            () => {
                const coletar = (seletor) => Array.from(document.querySelectorAll(seletor)).map(el => ({
                    tag: el.tagName,
                    id: el.id || null,
                    name: el.name || null,
                    type: el.type || null,
                    placeholder: el.placeholder || null,
                    texto: (el.innerText || el.value || '').trim().slice(0, 80) || null,
                }));
                return {
                    inputs: coletar('input'),
                    selects: coletar('select'),
                    buttons: coletar('button, input[type=submit], input[type=button]'),
                };
            }
            """
        )
        (OUTPUT_DIR / "campos_formulario.json").write_text(
            json.dumps(campos, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        (OUTPUT_DIR / "rede_pagina_inicial.json").write_text(
            json.dumps(network_log_inicial, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  -> {len(network_log_inicial)} chamadas de rede capturadas no carregamento")

        # --- tenta uma busca, se achar um campo de texto plausível ---
        current_log = network_log_busca
        texto_inputs = [
            c for c in campos["inputs"] if c["type"] in (None, "text", "search")
        ]
        if texto_inputs:
            candidato = texto_inputs[0]
            seletor = f"#{candidato['id']}" if candidato["id"] else f"input[name='{candidato['name']}']"
            print(f"Tentando digitar '{TERMO_TESTE}' em {seletor} ...")
            try:
                page.fill(seletor, TERMO_TESTE)
                page.wait_for_timeout(3000)
            except Exception as exc:
                print(f"  -> não consegui preencher automaticamente: {exc}")
        else:
            print("Nenhum campo de texto óbvio encontrado — pulei a tentativa de busca.")

        page.screenshot(path=str(OUTPUT_DIR / "pagina_apos_busca.png"), full_page=True)
        (OUTPUT_DIR / "rede_apos_busca.json").write_text(
            json.dumps(network_log_busca, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  -> {len(network_log_busca)} chamadas de rede capturadas após a tentativa de busca")

        browser.close()

    print(f"\nPronto. Confira a pasta '{OUTPUT_DIR}/' e me mande esses arquivos:")
    print("  - campos_formulario.json")
    print("  - rede_pagina_inicial.json")
    print("  - rede_apos_busca.json")
    print("  - (as duas capturas de tela, se puder)")


if __name__ == "__main__":
    main()
