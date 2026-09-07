$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.7_ARCHITECTURE_GATE_BRIDGE_DIAGNOSTIC.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function W {
    param([string]$Text)
    Write-Host $Text
    Add-Content $Report $Text -Encoding ASCII
}

W "D-OBSIDIAN-06.7 ARCHITECTURE GATE - KNOWLEDGE BRIDGE"
W ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss"))
W "READ-ONLY diagnostic. No files will be moved or modified."
W ""

$mainPy = ".\pyproject.toml"
$bridgeRoot = ".\iip_knowledge_bridge"
$bridgePy = ".\iip_knowledge_bridge\pyproject.toml"

if (-not (Test-Path $mainPy)) { throw "Main pyproject.toml not found." }
if (-not (Test-Path $bridgeRoot)) { throw "iip_knowledge_bridge not found." }

W "=== STRUCTURE ==="
W ("Main pyproject: " + (Resolve-Path $mainPy))
W ("Bridge root: " + (Resolve-Path $bridgeRoot))
W ("Bridge pyproject exists: " + (Test-Path $bridgePy))
W ""

W "=== MAIN pyproject package/entrypoint hints ==="
Select-String -Path $mainPy -Pattern "^\[project\]|^\[tool\.|name\s*=|packages|package-dir|py-modules|dependencies|include|exclude|iip" |
    ForEach-Object { W $_.Line }

W ""
W "=== BRIDGE pyproject package/entrypoint hints ==="
if (Test-Path $bridgePy) {
    Select-String -Path $bridgePy -Pattern "^\[project\]|^\[tool\.|name\s*=|packages|package-dir|py-modules|dependencies|include|exclude|iip" |
        ForEach-Object { W $_.Line }
}

W ""
W "=== DUPLICATE PYTHON MODULE TREE ==="
$mainKnowledge = Get-ChildItem ".\src\iip" -Recurse -File -Filter "*.py" -ErrorAction SilentlyContinue |
    ForEach-Object { $_.FullName.Substring((Resolve-Path ".\src").Path.Length + 1) } |
    Sort-Object

$bridgeSrc = Join-Path $bridgeRoot "src"
$bridgeIip = Join-Path $bridgeSrc "iip"
$bridgeKnowledge = Get-ChildItem $bridgeIip -Recurse -File -Filter "*.py" -ErrorAction SilentlyContinue |
    ForEach-Object { $_.FullName.Substring((Resolve-Path $bridgeSrc).Path.Length + 1) } |
    Sort-Object

$mainSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($x in $mainKnowledge) { [void]$mainSet.Add($x) }

$overlap = foreach ($x in $bridgeKnowledge) {
    if ($mainSet.Contains($x)) { $x }
}
$overlap = @($overlap)

W ("Main src/iip Python files: " + $mainKnowledge.Count)
W ("Bridge src/iip Python files: " + $bridgeKnowledge.Count)
W ("Exact relative-path overlaps: " + $overlap.Count)

if ($overlap.Count -gt 0) {
    $overlap | ForEach-Object { W ("OVERLAP: " + $_) }
}

W ""
W "=== IMPORT RESOLUTION FROM MAIN ROOT ==="

$probe = @'
from __future__ import annotations
import importlib.util
import json
import pathlib
import sys

mods = [
    "iip",
    "iip.knowledge",
    "iip.knowledge.event_adapter",
    "iip.knowledge.repository",
]

print("CWD=" + str(pathlib.Path.cwd()))
print("SYS_PATH_BEGIN")
for p in sys.path:
    print("  " + str(p))
print("SYS_PATH_END")

for name in mods:
    spec = importlib.util.find_spec(name)
    print(f"SPEC {name}: origin={getattr(spec, 'origin', None)} locations={getattr(spec, 'submodule_search_locations', None)}")

import iip
print("IMPORTED iip=" + str(pathlib.Path(iip.__file__).resolve()))

try:
    import iip.knowledge
    print("IMPORTED iip.knowledge=" + str(pathlib.Path(iip.knowledge.__file__).resolve()))
except Exception as exc:
    print("IMPORT iip.knowledge ERROR=" + repr(exc))

try:
    import iip.knowledge.repository
    print("IMPORTED iip.knowledge.repository=" + str(pathlib.Path(iip.knowledge.repository.__file__).resolve()))
except Exception as exc:
    print("IMPORT repository ERROR=" + repr(exc))
'@

$tmp = Join-Path $env:TEMP "iip_0670_import_probe.py"
Set-Content -Path $tmp -Value $probe -Encoding ASCII

python $tmp 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0670_import_probe.txt") |
    Tee-Object $Report -Append

$code = $LASTEXITCODE
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
if ($code -ne 0) {
    W ("Import probe exited with code " + $code)
}

W ""
W "=== INSTALLED DISTRIBUTION METADATA ==="
python -m pip show iip-platform 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0670_pip_show.txt") |
    Tee-Object $Report -Append

W ""
W "=== BRIDGE PACKAGE METADATA (if independently installable) ==="
Push-Location $bridgeRoot
try {
    python -m pip show iip-knowledge-bridge 2>&1 |
        Tee-Object (Join-Path $env:TEMP "iip_0670_bridge_pip_show.txt") |
        Tee-Object $Report -Append
}
finally {
    Pop-Location
}

W ""
W "=== GIT STATUS FOR ARCHITECTURE GATE ==="
git status --short 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0670_git_status.txt") |
    Tee-Object $Report -Append

W ""
W "STATUS: ARCHITECTURE GATE DIAGNOSTIC COMPLETE"
W "No source files were moved, deleted, or modified."
W ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

Write-Host ""
Write-Host "Relatório: $Report"
exit 0
