$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.7_ARCHITECTURE_GATE_BRIDGE_DIAGNOSTIC.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function W {
    param([string]$Text)
    Write-Host $Text
    Add-Content $Report $Text -Encoding ASCII
}

W "D-OBSIDIAN-06.7 ARCHITECTURE GATE - KNOWLEDGE BRIDGE FIX1"
W ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss"))
W "READ-ONLY diagnostic. No files will be moved or modified."
W ""

$mainPy = ".\pyproject.toml"

# Inventory shows the bridge nested under src\iip, not at repository root.
$candidates = @(
    ".\src\iip\iip_knowledge_bridge",
    ".\iip_knowledge_bridge",
    ".\src\iip_knowledge_bridge"
)

$bridgeRoot = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not (Test-Path $mainPy)) { throw "Main pyproject.toml not found." }
if (-not $bridgeRoot) {
    W "No bridge path candidate found."
    W "Candidates checked:"
    $candidates | ForEach-Object { W $_ }
    throw "iip_knowledge_bridge path not found."
}

$bridgePy = Join-Path $bridgeRoot "pyproject.toml"
$bridgeSrc = Join-Path $bridgeRoot "src"
$bridgeIip = Join-Path $bridgeSrc "iip"

W "Detected bridge path: $bridgeRoot"
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
W "=== NESTED PROJECT PATHS ==="
Get-ChildItem $bridgeRoot -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name |
    ForEach-Object { W $_.FullName }

W ""
W "=== DUPLICATE PYTHON MODULE TREE ==="

$mainSrc = Resolve-Path ".\src"
$mainIip = Join-Path $mainSrc "iip"

$mainFiles = @()
if (Test-Path $mainIip) {
    $mainFiles = Get-ChildItem $mainIip -Recurse -File -Filter "*.py" -ErrorAction SilentlyContinue |
        ForEach-Object {
            $_.FullName.Substring($mainIip.Length + 1)
        } |
        Sort-Object
}

$bridgeFiles = @()
if (Test-Path $bridgeIip) {
    $bridgeFiles = Get-ChildItem $bridgeIip -Recurse -File -Filter "*.py" -ErrorAction SilentlyContinue |
        ForEach-Object {
            $_.FullName.Substring($bridgeIip.Length + 1)
        } |
        Sort-Object
}

$mainSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($x in $mainFiles) { [void]$mainSet.Add($x) }

$overlap = @(
    foreach ($x in $bridgeFiles) {
        if ($mainSet.Contains($x)) { $x }
    }
)

W ("Main src/iip Python files: " + $mainFiles.Count)
W ("Bridge src/iip Python files: " + $bridgeFiles.Count)
W ("Exact relative-path overlaps: " + $overlap.Count)

$overlap | ForEach-Object { W ("OVERLAP: " + $_) }

W ""
W "=== IMPORT RESOLUTION FROM REPOSITORY ROOT ==="

$probe = @'
from __future__ import annotations
import importlib.util
import pathlib
import sys

mods = [
    "iip",
    "iip.knowledge",
    "iip.knowledge.repository",
    "iip.knowledge.event_adapter",
]

print("CWD=" + str(pathlib.Path.cwd()))
print("SYS_PATH_BEGIN")
for p in sys.path:
    print("  " + str(p))
print("SYS_PATH_END")

for name in mods:
    try:
        spec = importlib.util.find_spec(name)
        print(f"SPEC {name}: origin={getattr(spec, 'origin', None)} locations={getattr(spec, 'submodule_search_locations', None)}")
    except Exception as exc:
        print(f"SPEC {name}: ERROR={type(exc).__name__}: {exc}")

try:
    import iip
    print("IMPORTED iip=" + str(pathlib.Path(iip.__file__).resolve()))
except Exception as exc:
    print("IMPORT iip ERROR=" + repr(exc))

try:
    import iip.knowledge
    print("IMPORTED iip.knowledge=" + str(pathlib.Path(iip.knowledge.__file__).resolve()))
except Exception as exc:
    print("IMPORT iip.knowledge ERROR=" + repr(exc))
'@

$tmp = Join-Path $env:TEMP "iip_0670_import_probe_fix1.py"
Set-Content -Path $tmp -Value $probe -Encoding ASCII
Push-Location (Get-Location)
try {
    python $tmp 2>&1 |
        Tee-Object (Join-Path $env:TEMP "iip_0670_import_probe_fix1.txt") |
        Tee-Object $Report -Append
}
finally {
    Pop-Location
}
$code = $LASTEXITCODE
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

W ""
W "=== INSTALLED DISTRIBUTION METADATA ==="
python -m pip show iip-platform 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0670_pip_show_fix1.txt") |
    Tee-Object $Report -Append

W ""
W "=== BRIDGE DISTRIBUTION METADATA ==="
if (Test-Path $bridgeRoot) {
    python -m pip show iip-knowledge-bridge 2>&1 |
        Tee-Object (Join-Path $env:TEMP "iip_0670_bridge_pip_show_fix1.txt") |
        Tee-Object $Report -Append
}

W ""
W "STATUS: ARCHITECTURE GATE DIAGNOSTIC COMPLETE"
W ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
W "No source files were moved, deleted, or modified."
Write-Host ""
Write-Host "Relatório: $Report"
exit 0
