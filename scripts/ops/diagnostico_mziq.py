import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://realestate.patria.com/papel/pcip11/documentos/"

OUT = Path("data/patria/debug")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    responses = []

    def on_response(response):
        url = response.url

        if any(x in url.lower() for x in (
            "mziq",
            "api",
            "filemanager",
            "document",
            "documento",
            "category",
            "year",
        )):
            print(
                f"\n[RESPONSE] {response.status} {response.request.method} {url}",
                flush=True,
            )

            item = {
                "status": response.status,
                "method": response.request.method,
                "url": url,
                "resource_type": response.request.resource_type,
            }

            try:
                ct = response.headers.get("content-type", "")
                item["content_type"] = ct

                if "application/json" in ct or "text/json" in ct:
                    body = response.text()
                    item["body"] = body[:200000]

                    print(
                        f"[JSON] {body[:2000]}",
                        flush=True,
                    )
            except Exception as exc:
                item["body_error"] = repr(exc)

            responses.append(item)

    page.on("response", on_response)

    print(f"Abrindo: {URL}", flush=True)

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=120000,
    )

    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        pass

    print("\n[DIAGNÓSTICO] página carregada.", flush=True)
    print("[DIAGNÓSTICO] navegador ficará aberto.", flush=True)
    print("[DIAGNÓSTICO] Se aparecer o seletor, clique manualmente em 2019.", flush=True)
    print("[DIAGNÓSTICO] Depois aguarde alguns segundos.", flush=True)

    time.sleep(15)

    # Salva DOM
    (OUT / "mziq_page.html").write_text(
        page.content(),
        encoding="utf-8",
    )

    # Salva texto
    (OUT / "mziq_page.txt").write_text(
        page.locator("body").inner_text(),
        encoding="utf-8",
    )

    # Salva respostas
    (OUT / "mziq_responses.json").write_text(
        json.dumps(responses, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"\n[DIAGNÓSTICO] {len(responses)} respostas relevantes capturadas.",
        flush=True,
    )

    print(
        f"[DIAGNÓSTICO] Arquivo: {OUT / 'mziq_responses.json'}",
        flush=True,
    )

    time.sleep(5)

    browser.close()