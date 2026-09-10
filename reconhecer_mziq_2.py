"""Reconhecimento MZIQ, parte 2 — captura o CORPO das respostas da API.

A parte 1 já achou as URLs certas (apicatalog.mziq.com/filemanager/...).
Este script refaz a mesma navegação e desta vez salva o corpo (JSON) de
cada resposta que vier desse host, não só o status.

Rode com:
    python reconhecer_mziq_2.py "https://ri.abcbrasil.com.br/resultados/central-de-resultados/"

Gera mziq_reconhecimento/<slug>/respostas_apicatalog.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUTPUT_ROOT = Path("mziq_reconhecimento")


def slugify(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")[:80]


def main() -> None:
    if len(sys.argv) < 2:
        print('Uso: python reconhecer_mziq_2.py "URL_DA_PAGINA_DE_RESULTADOS"')
        sys.exit(1)

    url = sys.argv[1]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright não está instalado. Rode:\n"
            "  pip install playwright --break-system-packages\n"
            "  python -m playwright install chromium"
        )
        return

    output_dir = OUTPUT_ROOT / slugify(url)
    output_dir.mkdir(parents=True, exist_ok=True)

    capturas: list[dict] = []

    def on_response(response):
        if "apicatalog.mziq.com" not in response.url:
            return
        try:
            body = response.json()
        except Exception:
            try:
                body = response.text()
            except Exception:
                body = None
        capturas.append(
            {
                "url": response.url,
                "status": response.status,
                "request_method": response.request.method,
                "request_post_data": response.request.post_data,
                "body": body,
            }
        )
        print(f"  capturado: {response.url} -> status {response.status}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.on("response", on_response)

        print(f"Abrindo {url} ...")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)  # tempo generoso pra todas as chamadas completarem

        (output_dir / "respostas_apicatalog.json").write_text(
            json.dumps(capturas, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n{len(capturas)} resposta(s) de apicatalog.mziq.com salvas.")

        browser.close()

    print(f"Confira '{output_dir}/respostas_apicatalog.json' e me manda o conteúdo.")


if __name__ == "__main__":
    main()
