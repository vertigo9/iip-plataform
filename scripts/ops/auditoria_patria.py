#!/usr/bin/env python3
"""
Auditoria completa da coleta Patria/MZIQ.

Uso:
    python ".\auditoria_patria.py" --ticker PCI11

Opcional:
    python ".\auditoria_patria.py" --ticker PCI11 --output data/patria
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def detect_type(path: Path) -> str:
    try:
        with path.open("rb") as f:
            head = f.read(16)
    except Exception:
        return "UNREADABLE"

    if head.startswith(b"%PDF-"):
        return "PDF"
    if head.startswith(b"PK\x03\x04"):
        return "ZIP/OOXML"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "OLE"
    if head.startswith(b"<?xml") or head.lstrip().startswith(b"<?xml"):
        return "XML"
    if not head:
        return "EMPTY"

    try:
        sample = path.read_text(encoding="utf-8", errors="replace")[:2000]
        stripped = sample.lstrip()
        if stripped.startswith("<"):
            return "XML/TEXT"
        return "TEXT/BINARY"
    except Exception:
        return "BINARY"


def safe_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--output", default="data/patria")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    root = Path(args.output) / ticker
    manifest = root / "manifest.csv"
    audit_dir = root / "_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    if not manifest.exists():
        print(f"ERRO: manifesto não encontrado: {manifest}")
        return 2

    with manifest.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    files = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.name != "manifest.csv"
        and "_audit" not in p.parts
        and not p.name.startswith(".")
    ]

    by_sha = {}
    file_records = []
    unreadable = []
    zero_bytes = []

    print("=" * 78)
    print(f"AUDITORIA PATRIA/MZIQ — {ticker}")
    print("=" * 78)
    print(f"Manifesto : {manifest}")
    print(f"Registros : {len(rows)}")
    print(f"Arquivos  : {len(files)}")
    print()

    # Hash e validação física dos arquivos
    for p in files:
        try:
            size = p.stat().st_size
        except Exception:
            size = -1

        if size == 0:
            zero_bytes.append(str(p))
        typ = detect_type(p)
        digest = None
        if typ != "UNREADABLE":
            try:
                digest = sha256(p)
            except Exception:
                unreadable.append(str(p))
        else:
            unreadable.append(str(p))

        if digest:
            by_sha.setdefault(digest, []).append(p)

        file_records.append(
            {
                "file": str(p.relative_to(root)),
                "size": size,
                "type": typ,
                "sha256": digest or "",
            }
        )

    # Índices do manifesto
    manifest_sha = Counter()
    manifest_url = Counter()
    manifest_year = Counter()
    manifest_category = Counter()
    downloaded_rows = []
    missing_rows = []
    hash_mismatches = []

    for row in rows:
        y = row.get("year", "")
        cat = row.get("category", "")
        url = row.get("url", "")
        digest = (row.get("sha256") or "").strip()

        manifest_year[y] += 1
        manifest_category[cat] += 1
        if url:
            manifest_url[url] += 1

        if digest:
            manifest_sha[digest] += 1
            downloaded_rows.append(row)
        else:
            missing_rows.append(row)

    # Cada hash do manifesto deve existir fisicamente.
    for row in downloaded_rows:
        digest = row["sha256"].strip()
        paths = by_sha.get(digest, [])
        if not paths:
            hash_mismatches.append(
                {
                    "reason": "HASH_DO_MANIFESTO_NAO_ENCONTRADO_NO_DISCO",
                    "year": row.get("year", ""),
                    "category": row.get("category", ""),
                    "title": row.get("title", ""),
                    "url": row.get("url", ""),
                    "sha256": digest,
                }
            )

    # Duplicidades
    duplicate_urls = [{"url": u, "count": c} for u, c in manifest_url.items() if c > 1]
    duplicate_hashes = [
        {
            "sha256": h,
            "count": len(paths),
            "files": [str(p.relative_to(root)) for p in paths],
        }
        for h, paths in by_sha.items()
        if len(paths) > 1
    ]

    # Arquivos físicos que não aparecem no manifesto por hash.
    manifest_hash_set = set(manifest_sha)
    orphan_files = [
        r for r in file_records if r["sha256"] and r["sha256"] not in manifest_hash_set
    ]

    # Extensões/tipos
    type_counts = Counter(r["type"] for r in file_records)
    ext_counts = Counter(
        Path(r["file"]).suffix.lower() or "<sem extensão>" for r in file_records
    )

    # Por ano
    year_downloaded = Counter()
    for row in downloaded_rows:
        year_downloaded[row.get("year", "")] += 1

    # Gera CSV de inventário físico
    inventory_csv = audit_dir / "inventario_fisico.csv"
    with inventory_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "size", "type", "sha256"])
        w.writeheader()
        w.writerows(file_records)

    missing_csv = audit_dir / "nao_baixados.csv"
    with missing_csv.open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["ticker", "year", "category", "title", "url", "sha256"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in missing_rows:
            w.writerow({k: r.get(k, "") for k in fields})

    mismatch_json = audit_dir / "hash_mismatches.json"
    mismatch_json.write_text(
        json.dumps(hash_mismatches, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    duplicate_json = audit_dir / "duplicidades.json"
    duplicate_json.write_text(
        json.dumps(
            {"urls": duplicate_urls, "hashes": duplicate_hashes},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Relatório textual
    report = audit_dir / "relatorio.txt"
    with report.open("w", encoding="utf-8") as f:
        f.write(f"AUDITORIA PATRIA/MZIQ — {ticker}\n")
        f.write("=" * 78 + "\n\n")
        f.write(f"Registros no manifesto : {len(rows)}\n")
        f.write(f"Registros com SHA256   : {len(downloaded_rows)}\n")
        f.write(f"Registros sem SHA256   : {len(missing_rows)}\n")
        f.write(f"Arquivos físicos       : {len(files)}\n")
        f.write(f"Arquivos vazios        : {len(zero_bytes)}\n")
        f.write(f"Arquivos ilegíveis     : {len(unreadable)}\n")
        f.write(f"Hashes não encontrados : {len(hash_mismatches)}\n")
        f.write(f"URLs duplicadas        : {len(duplicate_urls)}\n")
        f.write(f"Hashes duplicados      : {len(duplicate_hashes)}\n")
        f.write(f"Arquivos órfãos        : {len(orphan_files)}\n\n")

        f.write("POR ANO — registrados / baixados\n")
        f.write("-" * 78 + "\n")
        for y in sorted(
            manifest_year,
            key=lambda x: safe_int(x) if safe_int(x) is not None else 99999,
        ):
            f.write(f"{y}: {manifest_year[y]} / {year_downloaded[y]}\n")

        f.write("\nPOR CATEGORIA\n")
        f.write("-" * 78 + "\n")
        for cat, n in manifest_category.most_common():
            f.write(f"{cat}: {n}\n")

        f.write("\nTIPOS FÍSICOS\n")
        f.write("-" * 78 + "\n")
        for typ, n in type_counts.most_common():
            f.write(f"{typ}: {n}\n")

        f.write("\nEXTENSÕES\n")
        f.write("-" * 78 + "\n")
        for ext, n in ext_counts.most_common():
            f.write(f"{ext}: {n}\n")

        if missing_rows:
            f.write("\nREGISTROS SEM DOWNLOAD\n")
            f.write("-" * 78 + "\n")
            for r in missing_rows:
                f.write(
                    f"{r.get('year','')} | {r.get('category','')} | "
                    f"{r.get('title','')} | {r.get('url','')}\n"
                )

        if zero_bytes:
            f.write("\nARQUIVOS VAZIOS\n")
            f.write("-" * 78 + "\n")
            f.write("\n".join(zero_bytes) + "\n")

        if hash_mismatches:
            f.write("\nHASHES DO MANIFESTO SEM ARQUIVO CORRESPONDENTE\n")
            f.write("-" * 78 + "\n")
            for x in hash_mismatches:
                f.write(f"{x['year']} | {x['title']} | {x['sha256']}\n")

        if duplicate_urls:
            f.write("\nURLs DUPLICADAS\n")
            f.write("-" * 78 + "\n")
            for x in duplicate_urls:
                f.write(f"{x['count']}x | {x['url']}\n")

        if duplicate_hashes:
            f.write("\nHASHES DUPLICADOS\n")
            f.write("-" * 78 + "\n")
            for x in duplicate_hashes:
                f.write(f"{x['count']}x | {x['sha256']}\n")
                for name in x["files"]:
                    f.write(f"    {name}\n")

        if orphan_files:
            f.write("\nARQUIVOS FÍSICOS ÓRFÃOS\n")
            f.write("-" * 78 + "\n")
            for x in orphan_files:
                f.write(f"{x['file']}\n")

    print("RESUMO")
    print("-" * 78)
    print(f"Manifesto:              {len(rows)} registros")
    print(f"Com SHA256:             {len(downloaded_rows)}")
    print(f"Sem download:           {len(missing_rows)}")
    print(f"Arquivos físicos:       {len(files)}")
    print(f"Arquivos vazios:        {len(zero_bytes)}")
    print(f"Hashes inconsistentes:  {len(hash_mismatches)}")
    print(f"URLs duplicadas:        {len(duplicate_urls)}")
    print(f"Hashes duplicados:      {len(duplicate_hashes)}")
    print(f"Arquivos órfãos:        {len(orphan_files)}")
    print()
    print("POR ANO (registrados / baixados)")
    for y in sorted(
        manifest_year, key=lambda x: safe_int(x) if safe_int(x) is not None else 99999
    ):
        print(f"  {y}: {manifest_year[y]} / {year_downloaded[y]}")
    print()
    print(f"Relatório : {report}")
    print(f"Inventário: {inventory_csv}")
    print(f"Pendentes : {missing_csv}")
    print(f"Duplicados: {duplicate_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
