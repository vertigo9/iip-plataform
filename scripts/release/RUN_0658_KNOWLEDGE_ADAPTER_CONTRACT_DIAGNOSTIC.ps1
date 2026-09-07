$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_KNOWLEDGE_ADAPTER_CONTRACT_DIAGNOSTIC.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.5 KNOWLEDGE ADAPTER CONTRACT DIAGNOSTIC",
    ("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Purpose: compare active adapter vs known patch adapter before production-runtime fix.",
    ""
) | Set-Content $Report -Encoding UTF8

$active = ".\src\iip\knowledge\event_adapter.py"
$patch = ".\src\iip\sources\patch\event_adapter.py"

Write-Host "=== File availability ==="
foreach ($f in $active,$patch) {
    $ok = Test-Path $f
    Write-Host "$f -> $ok"
    Add-Content $Report "$f -> $ok" -Encoding UTF8
}

Write-Host ""
Write-Host "=== Active adapter lifecycle definitions ==="
if (Test-Path $active) {
    Select-String -Path $active -Pattern "^\s*def\s+" |
        ForEach-Object {
            $line = "$($_.LineNumber):$($_.Line.Trim())"
            Write-Host $line
            Add-Content $Report ("ACTIVE " + $line) -Encoding UTF8
        }
}

Write-Host ""
Write-Host "=== Patch adapter lifecycle definitions ==="
if (Test-Path $patch) {
    Select-String -Path $patch -Pattern "^\s*def\s+" |
        ForEach-Object {
            $line = "$($_.LineNumber):$($_.Line.Trim())"
            Write-Host $line
            Add-Content $Report ("PATCH " + $line) -Encoding UTF8
        }
}

Write-Host ""
Write-Host "=== Relevant Runtime contract ==="
Get-Content ".\src\iip\core\__init__.py" |
    Select-Object -First 140 |
    ForEach-Object {
        Write-Host $_
        Add-Content $Report $_ -Encoding UTF8
    }

Write-Host ""
Write-Host "=== Runtime import inspection ==="
$probe = @'
from iip.knowledge.event_adapter import KnowledgeEventAdapter
import inspect

print("ACTIVE_ADAPTER=" + str(KnowledgeEventAdapter))
print("ACTIVE_MODULE=" + KnowledgeEventAdapter.__module__)
print("ACTIVE_SOURCE=" + str(inspect.getsourcefile(KnowledgeEventAdapter)))

for name in (
    "register","unregister","start","stop","initialize","setup",
    "attach","connect","subscribe","on_decision","on_snapshot","on_document"
):
    attr = getattr(KnowledgeEventAdapter, name, None)
    print(f"{name}={'YES' if callable(attr) else 'NO'}")

print("PUBLIC=" + ",".join(
    n for n in dir(KnowledgeEventAdapter)
    if not n.startswith("_") and callable(getattr(KnowledgeEventAdapter,n,None))
))
'@

$tmp = Join-Path $env:TEMP "iip_0658_adapter_contract.py"
Set-Content -Path $tmp -Value $probe -Encoding UTF8
python $tmp 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0658_adapter_contract.txt") |
    Tee-Object $Report -Append

$code = $LASTEXITCODE
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

Write-Host ""
if ($code -eq 0) {
    Write-Host "CONTRACT DIAGNOSTIC COMPLETE."
    Add-Content $Report "STATUS=COMPLETE" -Encoding UTF8
} else {
    Write-Host "CONTRACT DIAGNOSTIC FAILED exit=$code"
    Add-Content $Report "STATUS=FAILED exit=$code" -Encoding UTF8
}

Write-Host "Relatório: $Report"
