
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.4_DECISION_VALUATION_RECOMMENDATION_ACCEL.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.4 DECISION + VALUATION + RECOMMENDATION",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected release baseline: D-OBSIDIAN-06.3 / 95.48% / 739 passed / 4 skipped",
    "Previous 06.4 checkpoints: Analysis/Atlas/Cycle PASS; Analytics Core PASS",
    ""
) | Set-Content -Path $report -Encoding ASCII

$patterns = @(
    "decision",
    "valuation",
    "scoring",
    "recommendation",
    "portfolio_decision"
)

$files = @()
foreach ($pattern in $patterns) {
    Get-ChildItem ".\tests" -Filter "test_*.py" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*$pattern*" } |
        ForEach-Object { $files += $_.FullName }
}

$files = $files | Sort-Object -Unique

Write-Host ">>> discovered decision/value/recommendation tests: $($files.Count)"
("DISCOVERED_FILES=" + $files.Count) | Add-Content -Path $report -Encoding ASCII
$files | ForEach-Object { $_ | Add-Content -Path $report -Encoding ASCII }

if ($files.Count -eq 0) {
    "NO_DECISION_VALUATION_RECOMMENDATION_TESTS_FOUND=1" | Add-Content -Path $report -Encoding ASCII
    Write-Host "Nenhum teste encontrado."
    exit 2
}

Write-Host ">>> focused_execution"
">>> focused_execution" | Add-Content -Path $report -Encoding ASCII

& python -m pytest @files -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_0642_decision_value_recommendation.txt" |
    Tee-Object -FilePath $report -Append

$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII

if ($code -ne 0) {
    Write-Host "DECISION/VALUATION/RECOMMENDATION ACCELERATION FAILED"
    Write-Host "Relatório: $report"
    exit $code
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.4 DECISION + VALUATION + RECOMMENDATION PASS"
Write-Host "Relatório: $report"
