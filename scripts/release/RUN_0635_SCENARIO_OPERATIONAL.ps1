
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.3_SCENARIO_OPERATIONAL_SMOKE.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.3 SCENARIO + OPERATIONAL",
    ("Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.2 / 95.48% / 739 passed / 4 skipped",
    "Previous checkpoint: Knowledge + Intelligence smoke PASS",
    ""
) | Set-Content -Path $report -Encoding ASCII

$groups = @(
    @("scenario_engine", @(
        "DYNAMIC:scenario"
    )),
    @("operational_core", @(
        ".\tests\test_operational_101_200.py",
        ".\tests\test_operational_integration_22001_30000.py",
        ".\tests\test_operational_runtime.py",
        ".\tests\test_operational_integration.py"
    )),
    @("production_integration", @(
        ".\tests\test_production_integration_180001_220000.py",
        ".\tests\test_production_integration_release.py",
        ".\tests\test_production_integration_e2e.py"
    )),
    @("system_e2e", @(
        ".\tests\test_system_e2e.py",
        ".\tests\test_system_pipeline.py",
        ".\tests\test_xpml11_full_e2e.py"
    ))
)

foreach ($group in $groups) {
    $name = $group[0]
    $files = $group[1]

    Write-Host ">>> $name"
    (">>> " + $name) | Add-Content -Path $report -Encoding ASCII

    $existing = @()
    foreach ($f in $files) {
        if ($f -eq "DYNAMIC:scenario") {
            $existing += Get-ChildItem ".\tests" -Filter "test_*.py" -File |
                Where-Object { $_.Name -match "scenario" } |
                Select-Object -ExpandProperty FullName
        } elseif (Test-Path $f) {
            $existing += $f
        }
    }

    if ($existing.Count -eq 0) {
        Write-Host "Nenhum teste encontrado para $name"
        "NO_TEST_FILES_FOUND=1" | Add-Content -Path $report -Encoding ASCII
        exit 2
    }

    & python -m pytest @existing -q 2>&1 |
        Tee-Object -FilePath "$env:TEMP\iip_063_scenario_$name.txt" |
        Tee-Object -FilePath $report -Append

    $code = $LASTEXITCODE
    ("EXIT_CODE=" + $code) | Add-Content -Path $report -Encoding ASCII
    "" | Add-Content -Path $report -Encoding ASCII

    if ($code -ne 0) {
        Write-Host "SCENARIO/OPERATIONAL FAILED: $name"
        Write-Host "RelatÃ³rio: $report"
        exit $code
    }
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.3 SCENARIO + OPERATIONAL PASS"
Write-Host "RelatÃ³rio: $report"

