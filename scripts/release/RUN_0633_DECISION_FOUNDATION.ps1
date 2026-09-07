
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.3_DECISION_FOUNDATION_SMOKE.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.3 DECISION FOUNDATION",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.2 / 95.48% / 739 passed / 4 skipped",
    ""
) | Set-Content -Path $report -Encoding ASCII

$groups = @(
    @("decision_core", @(
        ".\tests\test_decision_301_500.py",
        ".\tests\test_decision_301_500.py"
    )),
    @("portfolio_decision", @(
        ".\tests\test_portfolio_decision_60001_70000.py",
        ".\tests\test_portfolio_decision_fix1.py",
        ".\tests\test_portfolio_decision_fix2.py",
        ".\tests\test_portfolio_decision_fix3_opportunity.py"
    )),
    @("strategy", @(
        ".\tests\test_strategy_70001_85000.py",
        ".\tests\test_strategy_contract_fix1.py",
        ".\tests\test_strategy_70001_85000.py",
        ".\tests\test_strategy_contract_fix1.py"
    )),
    @("orchestration", @(
        ".\tests\test_orchestration_16001_22000.py",
        ".\tests\test_orchestration_rebalancing_fix1.py"
    )),
    @("decision_e2e", @(
        ".\tests\test_integrated_portfolio_12001_16000.py",
        ".\tests\test_integrated_portfolio_pipeline.py",
        ".\tests\test_xpml11_full_e2e.py"
    ))
)

foreach ($group in $groups) {
    $name = $group[0]
    $files = $group[1]

    Write-Host ">>> $name"
    (">>> " + $name) | Add-Content -Path $report -Encoding ASCII

    & python -m pytest @files -q 2>&1 |
        Tee-Object -FilePath "$env:TEMP\iip_063_decision_$name.txt" |
        Tee-Object -FilePath $report -Append

    $code = $LASTEXITCODE
    ("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII
    "" | Add-Content -Path $report -Encoding ASCII

    if ($code -ne 0) {
        Write-Host "DECISION FOUNDATION FAILED: $name"
        Write-Host "RelatÃ³rio: $report"
        exit $code
    }
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.3 DECISION FOUNDATION PASS"
Write-Host "RelatÃ³rio: $report"



