"""Reconhecimento de sites de RI baseados em MZIQ (MZ Group) — genérico.

Objetivo: abrir a página de "Central de Resultados" de QUALQUER empresa
que use a plataforma MZIQ (reconhecível pelo rodapé "Powered by MZ" e
por assets em cdn-sites-assets.mziq.com), capturar as chamadas de rede
reais que a página faz para montar a grade de documentos, e salvar
tudo para eu desenhar um harvester genérico — parecido com o que já
existe para o Patria (harvest/patria.py), mas reutilizável para outras
empresas na mesma infraestrutura.

Rode com:
    python reconhecer_mziq.py "https://ri.abcbrasil.com.br/resultados/central-de-resultados/"

Ou para outra empresa, só troca a URL:
    python reconhecer_mziq.py "https://ri.outraempresa.com.br/resultados/"

Gera uma pasta `mziq_reconhecimento/<slug-da-url>/` com:
    - pagina.png            (screenshot depois de carregar)
    - pagina.html           (HTML completo)
    - rede.json             (todas as chamadas de rede — o que interessa
                              de verdade é filtrar por api.mziq.com aqui)
    - rede_mziq_apenas.json (só as chamadas para api.mziq.com, já filtradas)
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
        print('Uso: python reconhecer_mziq.py "URL_DA_PAGINA_DE_RESULTADOS"')
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

    network_log: list[dict] = []

    def on_request(request):
        entry = {
            "tipo": "request",
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
        }
        if request.method == "POST":
            try:
                entry["post_data"] = request.post_data
            except Exception:
                entry["post_data"] = None
        network_log.append(entry)

    def on_response(response):
        try:
            content_type = response.headers.get("content-type", "")
        except Exception:
            content_type = ""
        network_log.append(
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

        print(f"Abrindo {url} ...")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)  # tempo pro JS da grade de documentos montar

        print("Salvando screenshot e HTML...")
        page.screenshot(path=str(output_dir / "pagina.png"), full_page=True)
        (output_dir / "pagina.html").write_text(page.content(), encoding="utf-8")

        # tenta interagir com um seletor de ano, se existir, pra garantir
        # que a chamada de listagem aconteça de verdade
        try:
            selects = page.locator("select")
            if selects.count() > 0:
                print("Tentando mexer no seletor de ano encontrado...")
                selects.first.click()
                page.wait_for_timeout(2000)
        except Exception as exc:
            print(f"  (sem problema, seguindo sem isso: {exc})")

        page.wait_for_timeout(3000)

        (output_dir / "rede.json").write_text(
            json.dumps(network_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        mziq_only = [entry for entry in network_log if "mziq.com" in entry.get("url", "")]
        (output_dir / "rede_mziq_apenas.json").write_text(
            json.dumps(mziq_only, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"\n{len(network_log)} chamadas de rede no total")
        print(f"{len(mziq_only)} chamadas envolvendo mziq.com")

        browser.close()

    print(f"\nConfira '{output_dir}/' e me manda:")
    print("  - rede_mziq_apenas.json  (o mais importante)")
    print("  - pagina.png (se quiser, pra eu ver como ficou)")


if __name__ == "__main__":
    main()
