from __future__ import annotations

import argparse
import csv
import hashlib
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

DEFAULT_BASE = "https://realestate.patria.com/papel/{ticker}/documentos/"


@dataclass(frozen=True)
class Document:
    ticker: str
    year: int
    category: str
    title: str
    url: str
    sha256: str | None = None


def _safe_name(value: str) -> str:
    value = re.sub(r"[^\w\s.-]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()[:180]


class _ProgressPulse:
    """Mostra atividade durante downloads/requisições que podem demorar."""

    def __init__(self, prefix: str, interval: float = 0.5) -> None:
        self.prefix = prefix
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = time.monotonic()

    def __enter__(self):
        self._started = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        frames = "|/-\\"
        i = 0
        while not self._stop.wait(self.interval):
            elapsed = int(time.monotonic() - self._started)
            print(f"\r{self.prefix} {frames[i % len(frames)]} {elapsed:>3}s", end="", flush=True)
            i += 1

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        print("\r" + (" " * 100) + "\r", end="", flush=True)


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_year_select(page):
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            labels = [x.strip() for x in sel.locator("option").all_text_contents()]
            if any(re.fullmatch(r"(?:19|20)\d{2}", x) for x in labels):
                return sel
        except Exception:
            continue
    raise RuntimeError("Não encontrei o seletor de ano na Central de Documentos.")


def _category_for_link(link) -> str:
    # The page groups links under category headings. Walk up a few ancestors
    # and use the closest heading text when available.
    for ancestor in ["xpath=ancestor::*[self::section or self::div][1]",
                     "xpath=ancestor::*[self::section or self::div][2]"]:
        try:
            node = link.locator(ancestor)
            for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                heading = node.locator(tag).first
                if heading.count():
                    text = heading.inner_text().strip()
                    if text:
                        return text
        except Exception:
            pass
    return "Outros"


def _collect_links(page, ticker: str, year: int) -> list[Document]:
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
        if url in seen or not re.match(r"^https?://", url):
            continue
        # Keep likely document/download links and ignore navigation/social links.
        if not any(ext in low for ext in (".pdf", ".xlsx", ".xls", ".csv", ".xml", ".doc", ".docx", ".zip")):
            continue
        seen.add(url)
        documents.append(
            Document(
                ticker=ticker,
                year=year,
                category=_category_for_link(link),
                title=title or Path(url.split("?", 1)[0]).name,
                url=url,
            )
        )
    return documents


def _select_year(page, year: int) -> bool:
    sel = _find_year_select(page)
    values = sel.locator("option").all()
    wanted = str(year)
    for option in values:
        text = option.inner_text().strip()
        value = option.get_attribute("value")
        if text == wanted or value == wanted:
            sel.select_option(value=value if value is not None else text)
            page.wait_for_timeout(1000)
            return True
    return False


def harvest(
    ticker: str,
    years: range,
    output_dir: Path,
    headed: bool = False,
    base_url: str = DEFAULT_BASE,
) -> list[Document]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright não está instalado. Execute: "
            "python -m pip install -r .\\requirements-patria-harvester.txt "
            "e depois: python -m playwright install chromium"
        ) from exc

    ticker = ticker.upper()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[Document] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_page(accept_downloads=True)
        try:
            url = base_url.format(ticker=ticker.lower())
            print(f"Abrindo: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=120_000)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

            for year in years:
                print(f"Ano {year}: selecionando...", flush=True)
                if not _select_year(page, year):
                    print(f"Ano {year}: não disponível no site; pulando.", flush=True)
                    continue
                docs = _collect_links(page, ticker, year)
                print(f"Ano {year}: {len(docs)} links de documentos encontrados.", flush=True)
                print(f"  Iniciando coleta de {len(docs)} documentos...", flush=True)
                year_dir = output_dir / ticker / str(year)
                year_dir.mkdir(parents=True, exist_ok=True)

                for index, doc in enumerate(docs, start=1):
                    filename = _safe_name(doc.title) or Path(doc.url.split("?", 1)[0]).name or f"documento_{index}"
                    target = year_dir / filename
                    saved = False
                    try:
                        with _ProgressPulse(f"  [{index}/{len(docs)}] baixando {filename[:55]}"):
                            response = page.context.request.get(doc.url, timeout=30_000, fail_on_status_code=False)
                        if response.ok:
                            content_type = (response.headers.get("content-type") or "").lower()
                            body = response.body()
                            known_type = any(token in content_type for token in (
                                "application/pdf", "application/octet-stream", "application/vnd",
                                "text/csv", "application/xml", "text/xml", "application/zip",
                                "application/msword",
                            ))
                            known_ext = any(ext in doc.url.lower() for ext in (
                                ".pdf", ".xlsx", ".xls", ".csv", ".xml", ".doc", ".docx", ".zip"
                            ))
                            if body and (known_type or known_ext):
                                target.write_bytes(body)
                                saved = True
                    except Exception:
                        pass

                    if not saved:
                        # Fallback for endpoints that require a browser click.
                        try:
                            links_now = page.locator("a[href]")
                            for j in range(links_now.count()):
                                link = links_now.nth(j)
                                href = link.get_attribute("href")
                                if href and urljoin(page.url, href) == doc.url:
                                    with _ProgressPulse(f"  [{index}/{len(docs)}] aguardando download {filename[:45]}"):
                                        with page.expect_download(timeout=8_000) as info:
                                            link.click(timeout=8_000)
                                    download = info.value
                                    target = year_dir / _safe_name(download.suggested_filename or doc.title)
                                    download.save_as(str(target))
                                    saved = True
                                    break
                        except Exception:
                            pass

                    if saved and target.exists() and target.stat().st_size > 0:
                        results.append(Document(**{**asdict(doc), "sha256": _hash_file(target)}))
                        print(f"  [{index}/{len(docs)}] OK: {target.name}", flush=True)
                    else:
                        results.append(doc)
                        print(f"  [{index}/{len(docs)}] URL registrada: {doc.url}", flush=True)
        finally:
            browser.close()

    manifest = output_dir / ticker / "manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ticker", "year", "category", "title", "url", "sha256"],
        )
        writer.writeheader()
        writer.writerows(asdict(x) for x in results)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coleta documentos da Central Patria.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--years", required=True, help="Ex.: 2026 ou 2019-2026")
    parser.add_argument("--output", default="data/patria")
    parser.add_argument("--headed", action="store_true", help="Abre o Chromium visivelmente.")
    return parser


def _parse_years(value: str) -> range:
    if "-" in value:
        start, end = value.split("-", 1)
        return range(int(start), int(end) + 1)
    year = int(value)
    return range(year, year + 1)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    docs = harvest(
        ticker=args.ticker,
        years=_parse_years(args.years),
        output_dir=Path(args.output),
        headed=args.headed,
    )
    downloaded = sum(1 for doc in docs if doc.sha256)
    print(f"Documentos registrados: {len(docs)}")
    print(f"Downloads concluídos: {downloaded}")
    print(f"Manifesto: {Path(args.output) / args.ticker.upper() / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
