#!/usr/bin/env python3
"""
D-OBSIDIAN-06.11 R1 — CANDIDATE FORENSIC REVIEW

READ-ONLY / NON-DESTRUCTIVE.

Purpose:
  Forensically review:
    - 2 REMOVE-CANDIDATE records
    - 31 REVIEW duplicate groups
  from the validated D-OBSIDIAN-06.9 R1 decision set.

Evidence sources:
  - 06.9 Decision Matrix
  - 06.9 Canonicalization
  - 06.9 Duplicate Groups
  - 06.9 D Candidates
  - 06.9 Critical References (when present)

Additional read-only evidence:
  - current filesystem existence
  - current file size
  - current SHA-256
  - textual repository references to candidate paths
  - canonical path/existence
  - protection classification

IMPORTANT:
  This script DOES NOT remove, move, rename or modify files.
  It does not execute Git commands.
  It does not make an automatic deletion decision.

Decision labels are evidence classifications only:
  - NEEDS-APPROVAL
  - PRESERVE
  - REVIEW
  - ARCHIVE-CANDIDATE
  - REMOVE-CANDIDATE (SOURCE CLASSIFICATION ONLY)

No item is authorized for deletion by this script.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


EXPECTED = {
    "decision_total": 910,
    "remove_candidates": 2,
    "review_duplicate_rows": 126,
    "review_groups": 31,
    "duplicate_groups_total": 430,
    "has_canonical_groups": 63,
}


TEXT_EXTENSIONS = {
    ".py", ".ps1", ".psm1", ".psd1", ".txt", ".md", ".rst",
    ".json", ".jsonl", ".csv", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".conf", ".xml", ".html", ".htm", ".sql", ".sh",
    ".bat", ".cmd", ".gitignore", ".base",
}

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules",
}

PROTECTED_EXACT = {
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
}

PROTECTED_PREFIXES = (
    "data/",
    "vault/",
    "archive/",
    "tests/intelligence/",
    "tests/integration/",
)


def latest_file(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Fonte nao encontrada: {pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_value(row: dict[str, str], *names: str) -> str:
    lowered = {str(k).lower(): (v or "").strip() for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower(), "")
        if value:
            return value
    return ""


def norm_path(value: str, repo: Path) -> str:
    if not value:
        return ""

    p = value.strip().replace("\\", "/")
    repo_norm = str(repo).replace("\\", "/").rstrip("/")

    if p.lower().startswith(repo_norm.lower()):
        p = p[len(repo_norm):]

    # Handle ./ and leading separators without destroying legitimate names.
    p = p.lstrip("/")
    if p.startswith("./"):
        p = p[2:]

    return p


def full_path(value: str, repo: Path) -> Path | None:
    rel = norm_path(value, repo)
    if not rel:
        return None
    p = repo / Path(rel)
    return p


def protection(value: str, repo: Path) -> str:
    p = norm_path(value, repo).lower()
    if p in PROTECTED_EXACT:
        return "PROTECTED-CRITICAL"
    if p.startswith(PROTECTED_PREFIXES):
        return "PROTECTED"
    return "NORMAL"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_text_files(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for name in files:
            path = Path(root) / name
            rel = path.relative_to(repo).as_posix()

            # Never recursively scan generated forensic output directories.
            if rel.startswith("reports/D-OBSIDIAN-06.10-R4/"):
                continue
            if rel.startswith("reports/D-OBSIDIAN-06.10-R3/"):
                continue

            suffix = path.suffix.lower()
            if suffix in TEXT_EXTENSIONS or name.lower() in {".gitignore"}:
                yield path


def path_variants(value: str, repo: Path) -> set[str]:
    rel = norm_path(value, repo)
    if not rel:
        return set()

    variants = {rel, rel.replace("/", "\\")}

    if rel.startswith("./"):
        variants.add(rel[2:])

    return {v for v in variants if v}


def scan_references(repo: Path, target: str) -> tuple[int, list[str]]:
    """
    Conservative textual reference scan.

    It searches for:
      - normalized relative path
      - Windows-slash path
      - basename

    Basename hits are reported separately as weak evidence.
    """
    rel = norm_path(target, repo)
    if not rel:
        return 0, []

    basename = Path(rel).name
    variants = path_variants(rel, repo)

    strong_hits: set[str] = set()
    weak_hits: set[str] = set()

    for path in safe_text_files(repo):
        try:
            raw = path.read_bytes()
        except OSError:
            continue

        # Avoid treating binary files as text.
        if b"\x00" in raw[:8192]:
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                continue

        rel_source = path.relative_to(repo).as_posix()

        for variant in variants:
            if variant in text:
                strong_hits.add(rel_source)
                break

        if basename and basename in text and rel_source not in strong_hits:
            weak_hits.add(rel_source)

    # Strong references dominate; weak basename matches remain visible.
    result = [
        f"STRONG::{p}" for p in sorted(strong_hits)
    ] + [
        f"WEAK-BASENAME::{p}" for p in sorted(weak_hits)
        if p not in strong_hits
    ]

    return len(result), result


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def classify_candidate(
    *,
    source_decision: str,
    exists: bool,
    refs: int,
    protected: str,
    duplicate_rows: int,
    canonical_path: str,
    canonical_exists: bool,
) -> tuple[str, str]:
    if protected != "NORMAL":
        return (
            "PRESERVE",
            "Arquivo pertence a area protegida pelo contrato 06.10.",
        )

    if source_decision == "REMOVE-CANDIDATE":
        if exists and refs == 0 and not canonical_exists:
            return (
                "NEEDS-APPROVAL",
                "Candidato de remocao sem referencia textual detectada; "
                "existencia atual deve ser confirmada antes de qualquer acao.",
            )

        if not exists:
            return (
                "ALREADY-ABSENT",
                "O caminho classificado como candidato nao existe fisicamente "
                "na varredura atual.",
            )

        if refs > 0:
            return (
                "PRESERVE",
                "Ha referencias atuais; nao e seguro tratar como descartavel.",
            )

        return (
            "REVIEW",
            "Classificacao de origem nao e suficiente para autorizar remocao.",
        )

    if duplicate_rows > 0 and canonical_exists:
        return (
            "ARCHIVE-CANDIDATE",
            "Duplicidade com canonical existente; requer decisao de preservacao "
            "historica antes de qualquer limpeza.",
        )

    return (
        "REVIEW",
        "Evidencia insuficiente para classificacao automatica segura.",
    )


def main() -> int:
    repo = Path.cwd().resolve()
    source_dir = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    out_dir = repo / "reports" / "D-OBSIDIAN-06.11-R1"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    decision_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv"
    )
    canonical_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_CANONICALIZATION_*.csv"
    )
    duplicate_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_DUPLICATE_GROUPS_*.csv"
    )
    candidate_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_D_CANDIDATES_*.csv"
    )

    critical_files = list(
        source_dir.glob("D-OBSIDIAN-06.9_R1_CRITICAL_REFERENCES_*.csv")
    )
    critical_file = max(critical_files, key=lambda p: p.stat().st_mtime) if critical_files else None

    decision_rows = read_csv(decision_file)
    canonical_rows = read_csv(canonical_file)
    duplicate_rows = read_csv(duplicate_file)
    candidate_rows = read_csv(candidate_file)
    critical_rows = read_csv(critical_file) if critical_file else []

    print()
    print("=" * 88)
    print("D-OBSIDIAN-06.11 R1 - CANDIDATE FORENSIC REVIEW")
    print("=" * 88)
    print(f"Repository : {repo}")
    print(f"Output     : {out_dir}")
    print()
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("INPUT")
    print(f"  Decision       : {len(decision_rows)}")
    print(f"  Canonical      : {len(canonical_rows)}")
    print(f"  Duplicate      : {len(duplicate_rows)}")
    print(f"  Candidates     : {len(candidate_rows)}")
    print(f"  Critical refs  : {len(critical_rows)}")

    # Indexes
    canonical_by_hash: dict[str, list[dict[str, str]]] = {}
    decision_by_hash: dict[str, list[dict[str, str]]] = {}

    for row in canonical_rows:
        h = get_value(row, "Hash")
        if h:
            canonical_by_hash.setdefault(h, []).append(row)

    for row in decision_rows:
        h = get_value(row, "Hash")
        if h:
            decision_by_hash.setdefault(h, []).append(row)

    # ------------------------------------------------------------------
    # 1. REMOVE CANDIDATES
    # ------------------------------------------------------------------
    remove_rows = [
        row for row in decision_rows
        if get_value(row, "Decision") == "REMOVE-CANDIDATE"
    ]

    remove_report: list[dict] = []

    for row in remove_rows:
        h = get_value(row, "Hash")
        path_value = get_value(row, "Path")
        rel = norm_path(path_value, repo)
        fp = full_path(rel, repo)

        exists = bool(fp and fp.is_file())
        size = fp.stat().st_size if exists else 0
        current_hash = sha256_file(fp) if exists else ""

        matching_canonical = canonical_by_hash.get(h, [])
        canonical_paths = sorted({
            norm_path(get_value(r, "CanonicalPath"), repo)
            for r in matching_canonical
            if get_value(r, "CanonicalPath")
        })
        canonical_exists = any(
            bool(resolve := full_path(p, repo)) and resolve.is_file()
            for p in canonical_paths
        )

        refs_count, refs = scan_references(repo, rel) if exists else (0, [])

        source_refs = get_value(row, "References")
        duplicate_count = get_value(row, "DuplicateRows")
        policy = get_value(row, "Policy")
        source_reason = get_value(row, "Reason")

        prot = protection(rel, repo)
        final_class, rationale = classify_candidate(
            source_decision="REMOVE-CANDIDATE",
            exists=exists,
            refs=refs_count,
            protected=prot,
            duplicate_rows=int(duplicate_count or 0),
            canonical_path=" | ".join(canonical_paths),
            canonical_exists=canonical_exists,
        )

        remove_report.append({
            "Hash": h,
            "Path": rel,
            "ExistsNow": exists,
            "SizeBytesNow": size,
            "CurrentSHA256": current_hash,
            "Protection": prot,
            "SourceReferences": source_refs,
            "CurrentTextReferences": refs_count,
            "ReferenceEvidence": " || ".join(refs),
            "DuplicateRows": duplicate_count,
            "CanonicalPath": " | ".join(canonical_paths),
            "CanonicalExistsNow": canonical_exists,
            "Policy": policy,
            "SourceReason": source_reason,
            "ForensicClassification": final_class,
            "ForensicRationale": rationale,
            "DeletionAuthorized": False,
        })

    # ------------------------------------------------------------------
    # 2. REVIEW GROUPS
    # ------------------------------------------------------------------
    review_groups = [
        row for row in duplicate_rows
        if get_value(row, "GroupDecision") == "REVIEW"
    ]

    review_report: list[dict] = []

    for group in review_groups:
        h = get_value(group, "Hash")
        group_size = get_value(group, "GroupSize")

        matching_canonical = canonical_by_hash.get(h, [])
        matching_decision = decision_by_hash.get(h, [])

        paths = sorted({
            norm_path(get_value(r, "Path"), repo)
            for r in matching_canonical
            if get_value(r, "Path")
        })

        canonical_paths = sorted({
            norm_path(get_value(r, "CanonicalPath"), repo)
            for r in matching_canonical
            if get_value(r, "CanonicalPath")
        })

        statuses = sorted({
            get_value(r, "CanonicalStatus")
            for r in matching_canonical
            if get_value(r, "CanonicalStatus")
        })

        existing_paths = []
        protected_paths = []
        path_hashes = []

        for rel in paths:
            fp = full_path(rel, repo)
            if fp and fp.is_file():
                existing_paths.append(rel)
                try:
                    path_hashes.append(sha256_file(fp))
                except OSError:
                    pass
            if protection(rel, repo) != "NORMAL":
                protected_paths.append(rel)

        canonical_exists = any(
            bool(fp := full_path(rel, repo)) and fp.is_file()
            for rel in canonical_paths
        )

        # Current references for each member are deliberately bounded to
        # the exact relative path; this is evidence, not a delete decision.
        reference_details = []
        total_strong_refs = 0
        total_weak_refs = 0

        for rel in paths:
            if not rel:
                continue
            count, refs = scan_references(repo, rel)
            strong = sum(r.startswith("STRONG::") for r in refs)
            weak = sum(r.startswith("WEAK-BASENAME::") for r in refs)
            total_strong_refs += strong
            total_weak_refs += weak
            if refs:
                reference_details.append(
                    f"{rel} => " + " ; ".join(refs[:50])
                )

        decision_values = sorted({
            get_value(r, "Decision")
            for r in matching_decision
            if get_value(r, "Decision")
        })

        protected = "NORMAL"
        if protected_paths:
            protected = "PROTECTED"

        if protected != "NORMAL":
            classification = "PRESERVE"
            rationale = "Grupo contem caminhos pertencentes a area protegida."
        elif canonical_exists:
            classification = "ARCHIVE-CANDIDATE"
            rationale = (
                "Grupo REVIEW possui canonical fisicamente existente; "
                "preservar evidencia/historico ate decisao explicita."
            )
        elif existing_paths:
            classification = "REVIEW"
            rationale = (
                "Grupo REVIEW possui arquivos existentes, mas nao ha "
                "canonical fisicamente confirmada."
            )
        else:
            classification = "REVIEW"
            rationale = (
                "Nenhum membro existe fisicamente na varredura atual; "
                "manter registro para reconciliacao."
            )

        review_report.append({
            "Hash": h,
            "GroupSize": group_size,
            "GroupDecision": get_value(group, "GroupDecision"),
            "CanonicalRows": len(matching_canonical),
            "DecisionRows": len(matching_decision),
            "DecisionValues": " | ".join(decision_values),
            "CanonicalStatus": " | ".join(statuses),
            "Paths": " || ".join(paths),
            "ExistingPaths": " || ".join(existing_paths),
            "ProtectedPaths": " || ".join(protected_paths),
            "CanonicalPaths": " || ".join(canonical_paths),
            "CanonicalExistsNow": canonical_exists,
            "CurrentSHA256Set": " | ".join(sorted(set(path_hashes))),
            "StrongTextReferences": total_strong_refs,
            "WeakBasenameReferences": total_weak_refs,
            "ReferenceEvidence": " || ".join(reference_details),
            "ForensicClassification": classification,
            "ForensicRationale": rationale,
            "DeletionAuthorized": False,
        })

    # ------------------------------------------------------------------
    # 3. POPULATION / SAFETY CHECKS
    # ------------------------------------------------------------------
    checks: list[dict] = []

    def check(name: str, expected: int, actual: int):
        checks.append({
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        })

    check("DECISION_TOTAL", EXPECTED["decision_total"], len(decision_rows))
    check("REMOVE_CANDIDATES", EXPECTED["remove_candidates"], len(remove_rows))
    check(
        "REVIEW_DUPLICATE_ROWS",
        EXPECTED["review_duplicate_rows"],
        sum(
            get_value(r, "Decision") == "REVIEW-DUPLICATE"
            for r in decision_rows
        ),
    )
    check("REVIEW_GROUPS", EXPECTED["review_groups"], len(review_groups))
    check(
        "DUPLICATE_GROUPS_TOTAL",
        EXPECTED["duplicate_groups_total"],
        len(duplicate_rows),
    )

    has_canonical = {
        get_value(r, "Hash")
        for r in duplicate_rows
        if get_value(r, "GroupDecision") == "HAS-CANONICAL"
        and get_value(r, "Hash")
    }
    check(
        "HAS_CANONICAL_GROUPS",
        EXPECTED["has_canonical_groups"],
        len(has_canonical),
    )

    # All outputs must explicitly deny deletion authorization.
    unauthorized_delete_flags = sum(
        bool(row.get("DeletionAuthorized")) is not False
        for row in remove_report + review_report
    )
    check("NO_DELETION_AUTHORIZATION", 0, unauthorized_delete_flags)

    # Critical/protected presence
    for critical in sorted(PROTECTED_EXACT):
        actual = int((repo / Path(critical)).is_file())
        check(f"CRITICAL_EXISTS::{critical}", 1, actual)

    for tree in ("data", "vault", "archive", "tests/intelligence", "tests/integration"):
        actual = int((repo / Path(tree)).is_dir())
        check(f"PROTECTED_TREE::{tree}", 1, actual)

    # ------------------------------------------------------------------
    # 4. OUTPUTS
    # ------------------------------------------------------------------
    remove_out = out_dir / f"D-OBSIDIAN-06.11_R1_REMOVE_CANDIDATES_{timestamp}.csv"
    review_out = out_dir / f"D-OBSIDIAN-06.11_R1_REVIEW_GROUPS_{timestamp}.csv"
    checks_out = out_dir / f"D-OBSIDIAN-06.11_R1_CHECKS_{timestamp}.csv"
    summary_out = out_dir / f"D-OBSIDIAN-06.11_R1_SUMMARY_{timestamp}.txt"

    write_csv(remove_out, remove_report)
    write_csv(review_out, review_report)
    write_csv(checks_out, checks)

    failures = [c for c in checks if c["Status"] == "FAIL"]
    gate = len(failures) == 0

    classifications_remove = Counter(
        row["ForensicClassification"] for row in remove_report
    )
    classifications_review = Counter(
        row["ForensicClassification"] for row in review_report
    )

    summary: list[str] = []
    summary.append("D-OBSIDIAN-06.11 R1 - CANDIDATE FORENSIC REVIEW")
    summary.append("")
    summary.append("READ-ONLY / NON-DESTRUCTIVE")
    summary.append("")
    summary.append("INPUT")
    summary.append(f"Decision rows: {len(decision_rows)}")
    summary.append(f"Canonical rows: {len(canonical_rows)}")
    summary.append(f"Duplicate groups: {len(duplicate_rows)}")
    summary.append(f"Candidates: {len(candidate_rows)}")
    summary.append(f"Critical references: {len(critical_rows)}")
    summary.append("")
    summary.append("TARGET POPULATIONS")
    summary.append(f"REMOVE-CANDIDATE: {len(remove_rows)}")
    summary.append(f"REVIEW groups: {len(review_groups)}")
    summary.append("")
    summary.append("REMOVE-CANDIDATE FORENSIC CLASSIFICATION")
    for key in sorted(classifications_remove):
        summary.append(f"  [{classifications_remove[key]}] {key}")
    summary.append("")
    summary.append("REVIEW GROUP FORENSIC CLASSIFICATION")
    for key in sorted(classifications_review):
        summary.append(f"  [{classifications_review[key]}] {key}")
    summary.append("")
    summary.append("CHECKS")
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )
    summary.append("")
    summary.append("SAFETY")
    summary.append("No files removed.")
    summary.append("No files moved.")
    summary.append("No files renamed.")
    summary.append("No source contents modified.")
    summary.append("No git add.")
    summary.append("No git commit.")
    summary.append("No git restore.")
    summary.append("No git reset.")
    summary.append("No git clean.")
    summary.append("DeletionAuthorized is FALSE for every reviewed item.")
    summary.append("")
    summary.append(
        "FORENSIC REVIEW GATE: " + ("PASS" if gate else "FAIL")
    )

    summary_out.write_text("\n".join(summary) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # CONSOLE
    # ------------------------------------------------------------------
    print()
    print("=" * 88)
    print("D-OBSIDIAN-06.11 R1 - RESULTADO")
    print("=" * 88)
    print()
    print("TARGETS")
    print(f"  REMOVE-CANDIDATE : {len(remove_rows)}")
    print(f"  REVIEW GROUPS    : {len(review_groups)}")
    print()
    print("REMOVE-CANDIDATE CLASSIFICATION")
    for key in sorted(classifications_remove):
        print(f"  [{classifications_remove[key]}] {key}")
    print()
    print("REVIEW GROUP CLASSIFICATION")
    for key in sorted(classifications_review):
        print(f"  [{classifications_review[key]}] {key}")
    print()

    for c in checks:
        print(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )

    print()
    print("=" * 88)
    print("FORENSIC REVIEW GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out_dir}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
