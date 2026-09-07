
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.3_SYSTEM_GATE_ACCEL.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.3 SYSTEM GATE ACCELERATION",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.2 / 95.48% / 739 passed / 4 skipped",
    "Previous checkpoints: Decision / Knowledge+Intelligence / Scenario+Operational / Adaptive PASS",
    ""
) | Set-Content -Path $report -Encoding ASCII

$patterns = @(
    "system",
    "integration",
    "production",
    "repository",
    "source",
    "provider",
    "portfolio"
)

$files = @()
foreach ($pattern in $patterns) {
    Get-ChildItem ".\tests" -Filter "test_*.py" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*$pattern*" } |
        ForEach-Object { $files += $_.FullName }
}

$files = $files | Sort-Object -Unique

Write-Host ">>> discovered system-gate tests: $($files.Count)"
("DISCOVERED_FILES=" + $files.Count) | Add-Content -Path $report -Encoding ASCII
$files | ForEach-Object { $_ | Add-Content -Path $report -Encoding ASCII }

if ($files.Count -eq 0) {
    "NO_SYSTEM_GATE_TESTS_FOUND=1" | Add-Content -Path $report -Encoding ASCII
    Write-Host "Nenhum teste encontrado para a bateria system-gate."
    exit 2
}

Write-Host ">>> system_gate_execution"
">>> system_gate_execution" | Add-Content -Path $report -Encoding ASCII

& python -m pytest @files -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_063_system_gate.txt" |
    Tee-Object -FilePath $report -Append

$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII

if ($code -ne 0) {
    Write-Host "SYSTEM GATE ACCELERATION FAILED"
    Write-Host "Relatório: $report"
    exit $code
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.3 SYSTEM GATE ACCELERATION PASS"
Write-Host "Relatório: $report"
