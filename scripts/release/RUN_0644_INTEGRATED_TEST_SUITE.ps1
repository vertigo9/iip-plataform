
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.4_INTEGRATED_TEST_SUITE.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.4 INTEGRATED TEST SUITE",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.3 / 95.48% / 739 passed / 4 skipped",
    ""
) | Set-Content -Path $report -Encoding ASCII

Write-Host ">>> syntax_check"
python -m py_compile ".\tests\test_d064_integrated_suite.py" 2>&1 |
    Tee-Object -FilePath $report -Append

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ">>> integrated_suite"
python -m pytest ".\tests\test_d064_integrated_suite.py" -q 2>&1 |
    Tee-Object -FilePath $report -Append

$code = $LASTEXITCODE
("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII

if ($code -ne 0) {
    Write-Host "D-OBSIDIAN-06.4 INTEGRATED TEST SUITE FAILED"
    Write-Host "Relatório: $report"
    exit $code
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.4 INTEGRATED TEST SUITE PASS"
Write-Host "Relatório: $report"
