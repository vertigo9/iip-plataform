
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.3_FUNCTIONAL_SMOKE.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.3 FUNCTIONAL FOUNDATION",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Baseline: D-OBSIDIAN-06.2 / 95.48% / 739 passed / 4 skipped",
    ""
) | Set-Content -Path $report -Encoding ASCII

$groups = @(
    @("portfolio_policy", @(
        ".\tests\test_portfolio_source_policy.py",
        ".\tests\test_portfolio_source_router.py",
        ".\tests\test_portfolio_matrix_contract_fix1.py",
        ".\tests\test_portfolio_validation_import_fix1.py"
    )),
    @("provider_layer", @(
        ".\tests\test_provider_certification_runtime.py",
        ".\tests\test_provider_certification_runtime_fix1.py",
        ".\tests\test_provider_registry.py",
        ".\tests\test_provider_registry_health.py",
        ".\tests\test_provider_operations_api.py"
    )),
    @("integration_layer", @(
        ".\tests\test_integrated_portfolio_pipeline.py",
        ".\tests\test_integrated_portfolio_12001_16000.py",
        ".\tests\test_operational_integration_22001_30000.py",
        ".\tests\test_production_integration_180001_220000.py"
    )),
    @("e2e", @(
        ".\tests\test_xpml11_atlas_e2e.py",
        ".\tests\test_xpml11_full_e2e.py",
        ".\tests\test_post95_stabilization_700001_740000.py"
    ))
)

foreach ($group in $groups) {
    $name = $group[0]
    $files = $group[1]

    Write-Host ">>> $name"
    (">>> " + $name) | Add-Content -Path $report -Encoding ASCII

    & python -m pytest @files -q 2>&1 |
        Tee-Object -FilePath "$env:TEMP\iip_063_$name.txt" |
        Tee-Object -FilePath $report -Append

    $code = $LASTEXITCODE
    ("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII
    "" | Add-Content -Path $report -Encoding ASCII

    if ($code -ne 0) {
        Write-Host "FUNCTIONAL FOUNDATION FAILED: $name"
        Write-Host "Relatório: $report"
        exit $code
    }
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.3 FUNCTIONAL FOUNDATION PASS"
Write-Host "Relatório: $report"
