
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.3_RELEASE_CANDIDATE.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.3 RELEASE CANDIDATE",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.2 / 95.48% / 739 passed / 4 skipped",
    "System Gate Acceleration: 274 passed / 0 failures",
    ""
) | Set-Content -Path $report -Encoding ASCII

Write-Host ">>> collect_only"
">>> collect_only" | Add-Content -Path $report -Encoding ASCII
& python -m pytest --collect-only -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_063_collect.txt" |
    Tee-Object -FilePath $report -Append
$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII
"" | Add-Content -Path $report -Encoding ASCII
if ($code -ne 0) { exit $code }

Write-Host ">>> full_suite"
">>> full_suite" | Add-Content -Path $report -Encoding ASCII
& python -m pytest -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_063_full.txt" |
    Tee-Object -FilePath $report -Append
$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII
"" | Add-Content -Path $report -Encoding ASCII
if ($code -ne 0) { exit $code }

Write-Host ">>> coverage_gate_95"
">>> coverage_gate_95" | Add-Content -Path $report -Encoding ASCII
& python -m pytest --cov-fail-under=95 -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_063_cov.txt" |
    Tee-Object -FilePath $report -Append
$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII
"" | Add-Content -Path $report -Encoding ASCII
if ($code -ne 0) { exit $code }

Write-Host ""
Write-Host "D-OBSIDIAN-06.3 RELEASE CANDIDATE PASS"
Write-Host "Relatório: $report"
