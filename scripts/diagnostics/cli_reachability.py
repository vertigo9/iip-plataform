"""Mede quanto de ``src/iip`` o CLI realmente alcança, por pacote.

Segue os imports (estáticos, inclusive os feitos dentro de funções) a partir de
``iip.cli.main`` e conta módulos e linhas alcançados. Um pacote com 0 módulos alcançados
tem testes e código, mas nenhum comando o usa. Usado para o mapa em
``IIP_mapa_de_ligacao_ao_CLI.md``; rode da raiz do repositório:

    python scripts/diagnostics/cli_reachability.py
"""

from __future__ import annotations

import ast
import collections
from pathlib import Path

ROOT = Path("src")
ENTRY = "iip.cli.main"


def _modules() -> dict[str, Path]:
    found = {}
    for path in ROOT.rglob("*.py"):
        parts = list(path.relative_to(ROOT).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        found[".".join(parts)] = path
    return found


def _imports(name: str, path: Path, known: dict[str, Path]) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return {m for m in found if m in known}


def reachable(known: dict[str, Path]) -> set[str]:
    graph = {name: _imports(name, path, known) for name, path in known.items()}
    seen: set[str] = set()
    stack = [ENTRY]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        parts = name.split(".")
        parents = {".".join(parts[:i]) for i in range(1, len(parts))} & set(known)
        stack.extend(graph.get(name, set()) | parents)
    return seen


def main() -> None:
    known = _modules()
    seen = reachable(known)
    stats: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0, 0, 0])
    for name, path in known.items():
        if not name.startswith("iip."):
            continue
        package = name.split(".")[1]
        lines = sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
        stats[package][0] += 1
        stats[package][2] += lines
        if name in seen:
            stats[package][1] += 1
            stats[package][3] += lines
    modules = sum(s[0] for s in stats.values())
    reached = sum(s[1] for s in stats.values())
    lines = sum(s[2] for s in stats.values())
    reached_lines = sum(s[3] for s in stats.values())
    print(
        f"alcançados: {reached}/{modules} módulos, {reached_lines}/{lines} linhas "
        f"({reached_lines / lines:.0%})\n"
    )
    for package, (m, r, ln, rl) in sorted(stats.items(), key=lambda kv: -kv[1][2]):
        print(f"{package:28} {r:>3}/{m:<3} módulos  {rl:>5}/{ln:<5} linhas")
    print("\nnão alcançados:")
    for name in sorted(set(known) - seen):
        if name.startswith("iip."):
            print(f"  {name}")


if __name__ == "__main__":
    main()
