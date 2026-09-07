
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.3_ADAPTIVE_ACCEL_SMOKE.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.3 ADAPTIVE ACCELERATION",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.2 / 95.48% / 739 passed / 4 skipped",
    "Previous functional layers: Decision, Knowledge/Intelligence, Scenario/Operational PASS",
    ""
) | Set-Content -Path $report -Encoding ASCII

$patterns = @("adaptive", "anomaly", "signal_fusion", "decision_explanation", "portfolio_alerts", "refresh_policy", "run_registry", "source_priority")

$files = @()
foreach ($pattern in $patterns) {
    Get-ChildItem ".\tests" -Filter "test_*.py" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*$pattern*" } |
        ForEach-Object { $files += $_.FullName }
}

$files = $files | Sort-Object -Unique

Write-Host ">>> adaptive_discovery"
("Found adaptive-related test files: " + $files.Count) | Add-Content -Path $report -Encoding ASCII
$files | ForEach-Object { $_ | Add-Content -Path $report -Encoding ASCII }

if ($files.Count -eq 0) {
    Write-Host "Nenhum teste adaptativo encontrado."
    "NO_ADAPTIVE_TESTS_FOUND=1" | Add-Content -Path $report -Encoding ASCII
    exit 2
}

Write-Host ">>> adaptive_execution"
">>> adaptive_execution" | Add-Content -Path $report -Encoding ASCII

& python -m pytest @files -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_063_adaptive_accel.txt" |
    Tee-Object -FilePath $report -Append

$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII

if ($code -ne 0) {
    Write-Host "ADAPTIVE ACCELERATION FAILED"
    Write-Host "Relatório: $report"
    exit $code
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.3 ADAPTIVE ACCELERATION PASS"
Write-Host "Relatório: $report"
