
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.3_KNOWLEDGE_INTELLIGENCE_SMOKE.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.3 KNOWLEDGE + INTELLIGENCE",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.2 / 95.48% / 739 passed / 4 skipped",
    ""
) | Set-Content -Path $report -Encoding ASCII

$groups = @(
    @("knowledge_core", @(
        ".\tests\test_event_adapter.py",
        ".\tests\test_projection.py",
        ".\tests\test_vault.py",
        ".\tests\test_synchronization.py"
    )),
    @("knowledge_e2e", @(
        ".\tests\test_xpml11_full_e2e.py"
    )),
    @("intelligence_adjacent", @(
        ".\tests\test_health_extended.py",
        ".\tests\test_metrics.py",
        ".\tests\test_roundtrip.py"
    ))
)

foreach ($group in $groups) {
    $name = $group[0]
    $files = $group[1]

    Write-Host ">>> $name"
    (">>> " + $name) | Add-Content -Path $report -Encoding ASCII

    & python -m pytest @files -q 2>&1 |
        Tee-Object -FilePath "$env:TEMP\iip_063_knowledge_$name.txt" |
        Tee-Object -FilePath $report -Append

    $code = $LASTEXITCODE
    ("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII
    "" | Add-Content -Path $report -Encoding ASCII

    if ($code -ne 0) {
        Write-Host "KNOWLEDGE/INTELLIGENCE FAILED: $name"
        Write-Host "Relatório: $report"
        exit $code
    }
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.3 KNOWLEDGE + INTELLIGENCE PASS"
Write-Host "Relatório: $report"
