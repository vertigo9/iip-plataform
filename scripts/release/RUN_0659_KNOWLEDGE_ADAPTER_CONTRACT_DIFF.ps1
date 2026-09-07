$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_KNOWLEDGE_ADAPTER_CONTRACT_DIFF.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.5 KNOWLEDGE ADAPTER CONTRACT DIFF",
    ("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "READ-ONLY diagnostic. No source files will be changed.",
    ""
) | Set-Content $Report -Encoding UTF8

$active = ".\src\iip\knowledge\event_adapter.py"
$patch  = ".\src\iip\sources\patch\event_adapter.py"

if (-not (Test-Path $active)) { throw "Active adapter not found: $active" }
if (-not (Test-Path $patch))  { throw "Patch adapter not found: $patch" }

Write-Host "=== Active adapter ==="
Get-Content $active | Tee-Object $Report -Append

Write-Host ""
Write-Host "=== Patch adapter ==="
Get-Content $patch | Tee-Object $Report -Append

Write-Host ""
Write-Host "=== Unified diff (git-style) ==="

$diffScript = @'
from pathlib import Path
import difflib
import ast

active = Path(r"src/iip/knowledge/event_adapter.py").read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
patch = Path(r"src/iip/sources/patch/event_adapter.py").read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

for line in difflib.unified_diff(
    active, patch,
    fromfile="ACTIVE src/iip/knowledge/event_adapter.py",
    tofile="PATCH  src/iip/sources/patch/event_adapter.py",
):
    print(line, end="")

def methods(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8", errors="replace"))
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "KnowledgeEventAdapter":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[item.name] = ast.get_source_segment(
                        Path(path).read_text(encoding="utf-8", errors="replace"), item
                    )
    return out

a = methods("src/iip/knowledge/event_adapter.py")
p = methods("src/iip/sources/patch/event_adapter.py")

print("\n=== METHOD SIGNATURE/EXISTENCE MATRIX ===")
names = sorted(set(a) | set(p))
for name in names:
    print(f"{name}: ACTIVE={'YES' if name in a else 'NO'} PATCH={'YES' if name in p else 'NO'}")

print("\n=== REGISTER / UNREGISTER BODY COMPARISON ===")
for name in ("register", "unregister"):
    print(f"\n--- {name} ACTIVE ---")
    print(a.get(name, "<missing>"))
    print(f"--- {name} PATCH ---")
    print(p.get(name, "<missing>"))
'@

$tmp = Join-Path $env:TEMP "iip_0659_adapter_diff.py"
Set-Content -Path $tmp -Value $diffScript -Encoding UTF8

python $tmp 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0659_adapter_diff.txt") |
    Tee-Object $Report -Append

$code = $LASTEXITCODE
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

if ($code -ne 0) {
    Write-Host "DIFF diagnostic failed. Exit=$code"
    exit $code
}

Write-Host ""
Write-Host "DIFF diagnostic complete. Nenhuma alteração foi feita."
Write-Host "Relatório: $Report"
