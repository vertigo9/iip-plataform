
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.4_INTEGRATED_TEST_SUITE_PROGRESS.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

$started = Get-Date

@(
    "D-OBSIDIAN-06.4 INTEGRATED TEST SUITE - PROGRESS",
    ("Started: " + $started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.3 / 95.48%",
    ""
) | Set-Content -Path $report -Encoding ASCII

function Show-Status {
    param(
        [int]$Current,
        [int]$Total,
        [string]$Stage,
        [string]$Detail = ""
    )

    $pct = [math]::Round(($Current / $Total) * 100, 0)
    $elapsed = (Get-Date) - $started
    $elapsedText = "{0:hh\:mm\:ss}" -f $elapsed
    $barSize = 30
    $filled = [math]::Floor(($pct / 100) * $barSize)
    $bar = ("#" * $filled).PadRight($barSize, "-")

    Write-Host ("[{0}] {1,3}% | {2} | {3}" -f $bar, $pct, $Stage, $elapsedText)
    if ($Detail) { Write-Host ("    " + $Detail) }

    ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar, $pct, $Stage, $elapsedText, $Detail) |
        Add-Content -Path $report -Encoding ASCII
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.4 INTEGRATED TEST SUITE"
Write-Host "Status em tempo real por bloco"
Write-Host ""

Show-Status 0 3 "Preparando descoberta" "Carregando tests reais"

$testHarness = ".\tests\test_d064_integrated_suite.py"
if (-not (Test-Path $testHarness)) {
    Write-Host "ERRO: copie tests\test_d064_integrated_suite.py para .\tests\"
    exit 2
}

# Collect only first; this gives a quick health/status signal.
Show-Status 0 3 "Coleta" "Executando pytest --collect-only"
python -m pytest $testHarness --collect-only -q --no-cov 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_0644_collect.txt" |
    Tee-Object -FilePath $report -Append

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Show-Status 1 3 "Coleta concluÃ­da" "Harness reconhecido"

$bundles = @(
    @("analytics_decision", @(
        ".\tests\test_analysis_framework.py",
        ".\tests\test_agro_analyzer.py",
        ".\tests\test_infra_analyzer.py",
        ".\tests\test_portfolio_intelligence_50001_60000.py",
        ".\tests\test_decision_301_500.py",
        ".\tests\test_portfolio_decision_60001_70000.py",
        ".\tests\test_portfolio_decision_fix1.py",
        ".\tests\test_portfolio_decision_fix2.py",
        ".\tests\test_portfolio_decision_fix3_opportunity.py"
    )),
    @("knowledge_atlas", @(
        ".\tests\test_event_adapter.py",
        ".\tests\test_projection.py",
        ".\tests\test_synchronization.py",
        ".\tests\test_vault.py",
        ".\tests\test_atlas_document_adapter.py",
        ".\tests\test_atlas_history.py",
        ".\tests\test_atlas_knowledge_adapter.py",
        ".\tests\test_atlas_knowledge_id.py",
        ".\tests\test_atlas_knowledge_idempotency.py",
        ".\tests\test_xpml11_atlas_e2e.py",
        ".\tests\test_xpml11_full_e2e.py"
    )),
    @("adaptive_operational", @(
        ".\tests\test_health_extended.py",
        ".\tests\test_metrics.py",
        ".\tests\test_roundtrip.py",
        ".\tests\test_operational_101_200.py",
        ".\tests\test_operational_integration_22001_30000.py",
        ".\tests\test_production_integration_180001_220000.py",
        ".\tests\test_system_e2e.py"
    ))
)

$stage = 1

foreach ($bundle in $bundles) {
    $name = $bundle[0]
    $candidates = $bundle[1]
    $files = @()

    foreach ($f in $candidates) {
        if (Test-Path $f) { $files += $f }
    }

    Write-Host ""
    Show-Status $stage 3 $name ("Arquivos encontrados: " + $files.Count)

    if ($files.Count -eq 0) {
        Write-Host "ERRO: nenhum teste vÃ¡lido no bloco $name"
        Add-Content -Path $report -Value ("NO_TESTS_FOUND=" + $name) -Encoding ASCII
        exit 2
    }

    $bundleStart = Get-Date
    & python -m pytest @files -q 2>&1 |
        ForEach-Object {
            $_
            if ($_ -match "passed|failed|error|skipped") {
                Write-Host ("    " + $_)
            }
            $_ | Add-Content -Path $report -Encoding ASCII
        }

    $code = $LASTEXITCODE
    $bundleElapsed = (Get-Date) - $bundleStart
    $summary = "exit=$code elapsed={0}" -f ("{0:hh\:mm\:ss}" -f $bundleElapsed)
    Add-Content -Path $report -Value $summary -Encoding ASCII

    if ($code -ne 0) {
        Show-Status $stage 3 ($name + " FALHOU") $summary
        Write-Host "RelatÃ³rio: $report"
        exit $code
    }

    Show-Status ($stage + 1) 3 ($name + " PASSOU") $summary
    $stage++
}

Write-Host ""
Show-Status 3 3 "INTEGRATED SUITE PASS" "Todos os blocos concluÃ­dos"
Write-Host ""
Write-Host "RelatÃ³rio: $report"

