
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.4_ANALYTICS_CORE_ACCEL.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.4 ANALYTICS CORE ACCELERATION",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected release baseline: D-OBSIDIAN-06.3 / 95.48% / 739 passed / 4 skipped",
    "Previous 06.4 checkpoint: Analysis + Atlas + Cycle = 62 passed / 0 failures",
    ""
) | Set-Content -Path $report -Encoding ASCII

$patterns = @(
    "agro_analyzer",
    "infra_analyzer",
    "analysis_framework",
    "portfolio_intelligence"
)

$files = @()
foreach ($pattern in $patterns) {
    Get-ChildItem ".\tests" -Filter "test_*.py" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*$pattern*" } |
        ForEach-Object { $files += $_.FullName }
}

$files = $files | Sort-Object -Unique

Write-Host ">>> discovered analytics tests: $($files.Count)"
("DISCOVERED_FILES=" + $files.Count) | Add-Content -Path $report -Encoding ASCII
$files | ForEach-Object { $_ | Add-Content -Path $report -Encoding ASCII }

if ($files.Count -eq 0) {
    "NO_ANALYTICS_CORE_TESTS_FOUND=1" | Add-Content -Path $report -Encoding ASCII
    Write-Host "Nenhum teste de analytics core encontrado."
    exit 2
}

Write-Host ">>> analytics_core_execution"
">>> analytics_core_execution" | Add-Content -Path $report -Encoding ASCII

& python -m pytest @files -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_064_analytics_core.txt" |
    Tee-Object -FilePath $report -Append

$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII

if ($code -ne 0) {
    Write-Host "ANALYTICS CORE ACCELERATION FAILED"
    Write-Host "Relatório: $report"
    exit $code
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.4 ANALYTICS CORE ACCELERATION PASS"
Write-Host "Relatório: $report"
