
$ErrorActionPreference = "Stop"

$root = Get-Location
$report = Join-Path $root "D-OBSIDIAN-06.2_RELEASE_CERTIFICATION.txt"

Write-Host ""
Write-Host "=== D-OBSIDIAN-06.2 RELEASE CERTIFICATION ==="
Write-Host ""

$commands = @(
    @("collect", @("-m", "pytest", "--collect-only", "-q")),
    @("suite", @("-m", "pytest", "-q")),
    @("coverage_gate", @("-m", "pytest", "--cov-fail-under=95", "-q"))
)

Remove-Item $report -Force -ErrorAction SilentlyContinue

" D-OBSIDIAN-06.2 RELEASE CERTIFICATION" | Set-Content -Path $report -Encoding ASCII
("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) | Add-Content -Path $report -Encoding ASCII
"" | Add-Content -Path $report -Encoding ASCII

foreach ($item in $commands) {
    $label = $item[0]
    $args = $item[1]

    Write-Host ">>> $label"
    ">>> $label" | Add-Content -Path $report -Encoding ASCII

    & python @args 2>&1 | Tee-Object -FilePath "$env:TEMP\iip_release_$label.txt" |
        Tee-Object -FilePath $report -Append

    $code = $LASTEXITCODE
    ("EXIT_CODE=$code") | Add-Content -Path $report -Encoding ASCII
    "" | Add-Content -Path $report -Encoding ASCII

    if ($code -ne 0) {
        Write-Host "RELEASE CERTIFICATION FAILED at $label"
        Write-Host "Relatório: $report"
        exit $code
    }
}

Write-Host ""
Write-Host "RELEASE CERTIFICATION PASS"
Write-Host "Relatório: $report"
