
$ErrorActionPreference = "Stop"

$path = ".\RUN_0635_SCENARIO_OPERATIONAL.ps1"
if (-not (Test-Path $path)) {
    throw "Arquivo não encontrado: $path"
}

$text = Get-Content -Raw -Path $path

$old = @'
    @("scenario_engine", @(
        ".\tests\test_scenario_engine.py",
        ".\tests\test_scenario_engine_edge.py",
        ".\tests\test_scenario_engine_pipeline.py",
        ".\tests\test_scenario_engine_release.py"
    )),
'@

$new = @'
    @("scenario_engine", @(
        "DYNAMIC:scenario"
    )),
'@

if (-not $text.Contains($old.TrimEnd())) {
    throw "Bloco scenario_engine esperado não encontrado."
}

$text = $text.Replace($old.TrimEnd(), $new.TrimEnd())

$marker = @'
    $existing = @()
    foreach ($f in $files) {
        if (Test-Path $f) { $existing += $f }
    }
'@

$replacement = @'
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
'@

if (-not $text.Contains($marker.TrimEnd())) {
    throw "Bloco de descoberta de testes esperado não encontrado."
}

$text = $text.Replace($marker.TrimEnd(), $replacement.TrimEnd())
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX1 Scenario Operational aplicado."
Write-Host "scenario_engine agora descobre dinamicamente test_*.py contendo 'scenario'."
