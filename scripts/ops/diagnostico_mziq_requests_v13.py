from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_BASE = "https://realestate.patria.com/papel/{ticker}/documentos/"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Captura as requisições/respostas MZIQ da Central de Documentos."
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--wait", type=int, default=30)
    parser.add_argument("--output", default="data/patria/debug/mziq_requests_v13.json")
    args = parser.parse_args()

    url = DEFAULT_BASE.format(ticker=args.ticker.lower())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    requests = []
    responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # IMPORTANT: listeners are attached BEFORE navigation.
        def on_request(req):
            u = req.url
            if "apicatalog.mziq.com/" not in u:
                return
            item = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "method": req.method,
                "url": u,
                "resource_type": req.resource_type,
                "headers": dict(req.headers),
                "post_data": req.post_data,
            }
            try:
                item["post_data_json"] = req.post_data_json
            except Exception:
                item["post_data_json"] = None

            requests.append(item)

            print("\n[REQUEST MZIQ]")
            print(req.method, u)
            print("resource_type:", req.resource_type)
            print("POST DATA:", req.post_data)
            if req.post_data_json is not None:
                print("POST JSON:", req.post_data_json)

        def on_response(resp):
            u = resp.url
            if "apicatalog.mziq.com/" not in u:
                return

            item = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "status": resp.status,
                "method": resp.request.method,
                "url": u,
                "resource_type": resp.request.resource_type,
                "content_type": resp.headers.get("content-type", ""),
            }

            try:
                if "json" in item["content_type"].lower():
                    item["body"] = resp.json()
                else:
                    item["body"] = resp.text()[:20000]
            except Exception as exc:
                item["body_error"] = f"{type(exc).__name__}: {exc}"

            responses.append(item)

            print("\n[RESPONSE MZIQ]")
            print(resp.status, resp.request.method, u)
            print("content-type:", item["content_type"])
            body = item.get("body")
            if isinstance(body, dict):
                data = body.get("data")
                if isinstance(data, dict) and "document_metas" in data:
                    print("document_metas:", len(data["document_metas"]))
                print("JSON:", json.dumps(body, ensure_ascii=False)[:3000])
            else:
                print(str(body)[:3000])

        context.on("request", on_request)
        context.on("response", on_response)

        print(f"Abrindo: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)

        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass

        print("\n[DIAGNÓSTICO]")
        print("Página carregada.")
        print(f"Deixando o navegador aberto por {args.wait}s.")
        print("SE aparecer o seletor de ano, clique em 2019 manualmente.")
        print("O objetivo é capturar o POST exato que o site faz para 2019.")

        page.wait_for_timeout(args.wait * 1000)

        result = {
            "page_url": page.url,
            "captured_requests": requests,
            "captured_responses": responses,
        }
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("\n[RESULTADO]")
        print("Requests MZIQ capturados:", len(requests))
        print("Responses MZIQ capturadas:", len(responses))
        print("Arquivo:", output)

        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
