import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "src" / "iip" / "harvest" / "patria.py"

if not TARGET.exists():
    raise SystemExit(f"Arquivo não encontrado: {TARGET}")

src = TARGET.read_text(encoding="utf-8")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_name(f"patria.py.bak_v3_{stamp}")
shutil.copy2(TARGET, backup)


def replace_function(text, name, new_body):
    # Corrigido: o patch anterior tinha barras duplicadas na regex.
    pattern = re.compile(r"(?ms)^def " + re.escape(name) + r"\(.*?(?=^def |\Z)")
    m = pattern.search(text)
    if not m:
        raise RuntimeError(f"Não encontrei a função {name}() em {TARGET}")
    return text[: m.start()] + new_body.rstrip() + "\n\n" + text[m.end() :]


new_find_year = r"""def _find_year_select(page):
    selects = page.locator("select")
    count = selects.count()

    for i in range(count):
        sel = selects.nth(i)
        try:
            labels = [
                (x or "").strip()
                for x in sel.locator("option").all_text_contents()
            ]
            values = [
                (x or "").strip()
                for x in sel.locator("option").evaluate_all(
                    "(opts) => opts.map(o => o.value || '')"
                )
            ]

            if any(re.fullmatch(r"(?:19|20)\d{2}", x) for x in labels):
                return sel
            if any(re.fullmatch(r"(?:19|20)\d{2}", x) for x in values):
                return sel
        except Exception:
            continue

    print(f"[DIAGNÓSTICO] selects encontrados: {count}", flush=True)
    raise RuntimeError("Não encontrei o seletor de ano na Central de Documentos.")
"""

new_collect = r"""def _collect_links(page, ticker: str, year: int) -> list[Document]:
    links = page.locator("a[href]")
    seen: set[str] = set()
    documents: list[Document] = []

    for i in range(links.count()):
        link = links.nth(i)
        try:
            href = link.get_attribute("href")
            title = (link.inner_text() or "").strip()
        except Exception:
            continue

        if not href:
            continue

        url = urljoin(page.url, href)
        low = url.lower()

        if not re.match(r"^https?://", url):
            continue

        # Documentos antigos do Patria usam MZ File Manager sem .pdf
        # no href, por exemplo: api.mziq.com/mzfilemanager/v2/d/.../UUID
        is_mz_document = "api.mziq.com/mzfilemanager/" in low

        is_file_extension = any(
            ext in low
            for ext in (
                ".pdf", ".xlsx", ".xls", ".csv", ".xml",
                ".doc", ".docx", ".zip"
            )
        )

        if not (is_mz_document or is_file_extension):
            continue

        if url in seen:
            continue

        seen.add(url)

        if not title:
            title = (
                Path(url.split("?", 1)[0]).name
                or f"{ticker}_{year}_{len(documents) + 1}"
            )

        documents.append(
            Document(
                ticker=ticker,
                year=year,
                category=_category_for_link(link),
                title=title,
                url=url,
            )
        )

    return documents
"""

new_select_year = r"""def _select_year(page, year: int) -> bool:
    sel = _find_year_select(page)
    wanted = str(year)

    options = sel.locator("option")
    count = options.count()

    for i in range(count):
        option = options.nth(i)
        try:
            text = (option.inner_text() or "").strip()
            value = (option.get_attribute("value") or "").strip()

            if text == wanted or value == wanted:
                sel.select_option(value or text)
                page.wait_for_timeout(800)
                return True
        except Exception:
            continue

    return False
"""

for name, body in [
    ("_find_year_select", new_find_year),
    ("_collect_links", new_collect),
    ("_select_year", new_select_year),
]:
    src = replace_function(src, name, body)

TARGET.write_text(src, encoding="utf-8")

print("PATCH V3 CORRIGIDO APLICADO COM SUCESSO")
print(f"Arquivo: {TARGET}")
print(f"Backup:  {backup}")
print()
print("Teste:")
print(r'python ".\scripts\patria_harvester.py" --ticker PCIP11 --years 2019 --headed')
