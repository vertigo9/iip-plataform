
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.4_DECISION_EDGE_HARDENING.txt"
$backup = ".\RUN_0643_DECISION_EDGE_HARDENING.ps1.bak"
$runner = ".\RUN_0643_DECISION_EDGE_HARDENING.ps1"

if (Test-Path $runner) {
    Copy-Item $runner $backup -Force
}

$newRunner = @'
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.4_DECISION_EDGE_HARDENING.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.4 DECISION EDGE HARDENING FIX2",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.3 / 95.48% / 739 passed / 4 skipped",
    "Discovery mode: test content references target implementation modules",
    ""
) | Set-Content -Path $report -Encoding ASCII

$targets = @(
    "iip.decision.decision_engine",
    "iip.decision.validation",
    "iip.decision.valuation_bridge",
    "decision_engine",
    "valuation_bridge"
)

$files = @()

Get-ChildItem ".\tests" -Filter "test_*.py" -File -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object {
        $matched = Select-String -Path $_.FullName -Pattern $targets -SimpleMatch -Quiet -ErrorAction SilentlyContinue
        if ($matched) {
            $files += $_.FullName
        }
    }

$files = $files | Sort-Object -Unique

Write-Host ">>> content_discovery"
("DISCOVERED_FILES=" + $files.Count) | Add-Content -Path $report -Encoding ASCII
$files | ForEach-Object { $_ | Add-Content -Path $report -Encoding ASCII }

if ($files.Count -eq 0) {
    "NO_DECISION_EDGE_TESTS_FOUND=1" | Add-Content -Path $report -Encoding ASCII
    Write-Host "Nenhum teste foi encontrado por referência de conteúdo aos módulos-alvo."
    exit 2
}

Write-Host ">>> focused_execution"
">>> focused_execution" | Add-Content -Path $report -Encoding ASCII

& python -m pytest @files -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_0643_fix2_decision_edge.txt" |
    Tee-Object -FilePath $report -Append

$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII

if ($code -ne 0) {
    Write-Host "DECISION EDGE HARDENING FAILED"
    Write-Host "Relatório: $report"
    exit $code
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.4 DECISION EDGE HARDENING PASS"
Write-Host "Relatório: $report"
'@

Set-Content -Path $runner -Value $newRunner -Encoding utf8

Write-Host "FIX2 Decision Edge aplicado com sucesso."
Write-Host "O executor agora descobre testes pelo conteúdo, não pelo nome."
Write-Host "Backup criado: $backup"
