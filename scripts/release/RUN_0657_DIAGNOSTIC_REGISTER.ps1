$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_PRODUCTION_SMOKE_DIAGNOSTIC_REGISTER.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.5 PRODUCTION SMOKE - REGISTER DIAGNOSTIC",
    ("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Purpose: identify the KnowledgeEventAdapter lifecycle method before changing production code.",
    ""
) | Set-Content $Report -Encoding UTF8

Write-Host "=== Runtime.start / KnowledgeEventAdapter diagnostic ==="

$files = @(
    ".\src\iip\core\__init__.py"
)

$adapterMatches = Get-ChildItem .\src -Recurse -File -ErrorAction SilentlyContinue |
    Select-String -Pattern "KnowledgeEventAdapter|class .*EventAdapter|def register\(|def start\(|def initialize\(|def setup\(|def attach\(|def connect\("

Write-Host ""
Write-Host "--- Matching source locations ---"
$adapterMatches | ForEach-Object {
    $line = "$($_.Path):$($_.LineNumber):$($_.Line.Trim())"
    Write-Host $line
    Add-Content $Report $line -Encoding UTF8
}

Write-Host ""
Write-Host "--- core Runtime source ---"
if (Test-Path $files[0]) {
    Get-Content $files[0] | Select-Object -First 140 | ForEach-Object {
        Write-Host $_
        Add-Content $Report $_ -Encoding UTF8
    }
} else {
    Write-Host "core source not found"
    Add-Content $Report "core source not found" -Encoding UTF8
}

Write-Host ""
Write-Host "--- importing adapter and listing lifecycle methods ---"

$script = @'
from __future__ import annotations
import inspect

try:
    from iip.events import KnowledgeEventAdapter
except Exception as exc:
    print(f"IMPORT_EVENTS_ERROR={type(exc).__name__}: {exc}")
    raise

print(f"ADAPTER_CLASS={KnowledgeEventAdapter.__module__}.{KnowledgeEventAdapter.__name__}")
print("PUBLIC_METHODS=" + ",".join(
    n for n in dir(KnowledgeEventAdapter)
    if not n.startswith("_") and callable(getattr(KnowledgeEventAdapter, n, None))
))

for name in ("register", "start", "initialize", "setup", "attach", "connect", "subscribe"):
    attr = getattr(KnowledgeEventAdapter, name, None)
    print(f"METHOD_{name}={'YES' if callable(attr) else 'NO'}")

try:
    print("SOURCE_FILE=" + inspect.getsourcefile(KnowledgeEventAdapter))
except Exception:
    pass

try:
    print("SIGNATURE=" + str(inspect.signature(KnowledgeEventAdapter)))
except Exception:
    pass
'@

$tmp = Join-Path $env:TEMP "iip_0657_adapter_diag.py"
Set-Content -Path $tmp -Value $script -Encoding UTF8

python $tmp 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0657_adapter_diag.txt") |
    Tee-Object $Report -Append

$code = $LASTEXITCODE

Remove-Item $tmp -Force -ErrorAction SilentlyContinue

Write-Host ""
if ($code -eq 0) {
    Write-Host "DIAGNOSTIC COMPLETE. Nenhuma alteração foi feita no código de produção."
    Add-Content $Report "DIAGNOSTIC_COMPLETE=1" -Encoding UTF8
} else {
    Write-Host "DIAGNOSTIC falhou ao importar o adapter. Exit=$code"
    Add-Content $Report "DIAGNOSTIC_EXIT=$code" -Encoding UTF8
}

Write-Host "Relatório: $Report"
exit $code
