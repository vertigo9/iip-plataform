param(
    [string]$VaultPath = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " IIP OBSIDIAN VAULT - INTEGRITY VALIDATOR" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Pass($msg) {
    Write-Host "PASS: $msg" -ForegroundColor Green
}

function Fail($msg) {
    Write-Host "FAIL: $msg" -ForegroundColor Red
    $script:failures.Add($msg)
}

function Warn($msg) {
    Write-Host "WARN: $msg" -ForegroundColor Yellow
    $script:warnings.Add($msg)
}

# --------------------------------------------------
# 1. Estrutura
# --------------------------------------------------

Write-Host "===== ESTRUTURA =====" -ForegroundColor Cyan

$folders = @(
    "00_System",
    "01_Assets",
    "02_Portfolio",
    "03_Decisions",
    "04_Evidence",
    "05_Events",
    "06_Exposures",
    "07_Research",
    "08_Dashboards"
)

foreach ($folder in $folders) {

    $path = Join-Path $VaultPath $folder

    if (Test-Path -LiteralPath $path) {
        Pass $folder
    }
    else {
        Fail "Pasta ausente: $folder"
    }
}

# --------------------------------------------------
# 2. Templates
# --------------------------------------------------

Write-Host ""
Write-Host "===== TEMPLATES =====" -ForegroundColor Cyan

$templates = @(
    "03_Decisions\DECISION-TEMPLATE.md",
    "04_Evidence\EVIDENCE-TEMPLATE.md",
    "05_Events\EVENT-TEMPLATE.md"
)

foreach ($template in $templates) {

    $path = Join-Path $VaultPath $template

    if (-not (Test-Path -LiteralPath $path)) {
        Fail "Template inexistente: $template"
        continue
    }

    $lines = Get-Content -LiteralPath $path -Encoding UTF8
    $content = Get-Content -LiteralPath $path -Raw -Encoding UTF8

    $yamlStart = $false
    $yamlEnd = $false

    if ($lines.Count -gt 0 -and $lines[0].Trim() -eq "---") {
        $yamlStart = $true
    }

    for ($i = 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq "---") {
            $yamlEnd = $true
            break
        }
    }

    if ($yamlStart -and $yamlEnd) {
        Pass "YAML: $template"
    }
    else {
        Fail "YAML inválido: $template"
    }

    if (-not $content.Contains("\_")) {
        Pass "Sem escape indevido: $template"
    }
    else {
        Fail "Contém \_: $template"
    }
}

# --------------------------------------------------
# 3. Coleta de documentos
# --------------------------------------------------

Write-Host ""
Write-Host "===== DOCUMENTOS =====" -ForegroundColor Cyan

$decisionFiles = Get-ChildItem `
    (Join-Path $VaultPath "03_Decisions") `
    -Filter "*.md" `
    -File |
    Where-Object { $_.Name -notmatch "TEMPLATE|\.bak$|\.pre-fix$" }

$evidenceFiles = Get-ChildItem `
    (Join-Path $VaultPath "04_Evidence") `
    -Filter "*.md" `
    -File |
    Where-Object { $_.Name -notmatch "TEMPLATE" }

Pass "Decisions encontradas: $($decisionFiles.Count)"
Pass "Evidence encontradas: $($evidenceFiles.Count)"

# --------------------------------------------------
# 4. IDs
# --------------------------------------------------

Write-Host ""
Write-Host "===== IDS =====" -ForegroundColor Cyan

$ids = @{}

foreach ($file in $decisionFiles + $evidenceFiles) {

    $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8

    $idMatch = [regex]::Match(
        $content,
        '(?m)^(decision_id|evidence_id):\s*(.+)$'
    )

    if (-not $idMatch.Success) {
        Fail "ID ausente: $($file.Name)"
        continue
    }

    $id = $idMatch.Groups[2].Value.Trim()

    if ([string]::IsNullOrWhiteSpace($id)) {
        Fail "ID vazio: $($file.Name)"
        continue
    }

    if ($ids.ContainsKey($id)) {
        Fail "ID duplicado: $id"
    }
    else {
        $ids[$id] = $file.FullName
        Pass "ID: $id"
    }
}

# --------------------------------------------------
# 5. Ticker
# --------------------------------------------------

Write-Host ""
Write-Host "===== TICKER =====" -ForegroundColor Cyan

foreach ($file in $decisionFiles + $evidenceFiles) {

    $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8

    if ($content -match "(?m)^ticker:\s*(.+)$") {

        $ticker = $Matches[1].Trim()

        if ($ticker -eq "PCPI11") {
            Fail "Ticker incorreto PCPI11 em: $($file.Name)"
        }
        else {
            Pass "Ticker $ticker: $($file.Name)"
        }
    }
}

# --------------------------------------------------
# 6. Links internos
# --------------------------------------------------

Write-Host ""
Write-Host "===== LINKS INTERNOS =====" -ForegroundColor Cyan

$allMarkdown = Get-ChildItem `
    $VaultPath `
    -Recurse `
    -Filter "*.md" `
    -File

foreach ($file in $allMarkdown) {

    $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8

    $matches = [regex]::Matches(
        $content,
        '\[\[([^\]]+)\]\]'
    )

    foreach ($match in $matches) {

        $target = $match.Groups[1].Value.Trim()

        if ($target -match '\|') {
            $target = $target.Split('|')[0].Trim()
        }

        $possible = @(
            (Join-Path $file.DirectoryName "$target.md"),
            (Join-Path $VaultPath "$target.md")
        )

        $found = $false

        foreach ($candidate in $possible) {
            if (Test-Path -LiteralPath $candidate) {
                $found = $true
                break
            }
        }

        if ($found) {
            Pass "Link OK: $($file.Name) -> $target"
        }
        else {
            Fail "Link quebrado: $($file.Name) -> $target"
        }
    }
}

# --------------------------------------------------
# 7. Verificação específica PCIP11
# --------------------------------------------------

Write-Host ""
Write-Host "===== PCIP11 ROUNDTRIP =====" -ForegroundColor Cyan

$pcipDecisions = $decisionFiles |
    Where-Object { $_.Name -match "PCIP11" }

$pcipEvidence = $evidenceFiles |
    Where-Object { $_.Name -match "PCIP11" }

if ($pcipDecisions.Count -gt 0) {
    Pass "Decisions PCIP11: $($pcipDecisions.Count)"
}
else {
    Fail "Nenhuma Decision PCIP11 encontrada"
}

if ($pcipEvidence.Count -gt 0) {
    Pass "Evidence PCIP11: $($pcipEvidence.Count)"
}
else {
    Fail "Nenhuma Evidence PCIP11 encontrada"
}

# --------------------------------------------------
# 8. Resumo
# --------------------------------------------------

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " RESUMO FINAL" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

Write-Host ""

if ($failures.Count -eq 0) {
    Write-Host "INTEGRIDADE: PASS" -ForegroundColor Green
}
else {
    Write-Host "INTEGRIDADE: FAIL" -ForegroundColor Red
}

Write-Host "Falhas: $($failures.Count)"
Write-Host "Warnings: $($warnings.Count)"

if ($failures.Count -gt 0) {

    Write-Host ""
    Write-Host "===== FALHAS =====" -ForegroundColor Red

    foreach ($failure in $failures) {
        Write-Host "- $failure" -ForegroundColor Red
    }
}

if ($warnings.Count -gt 0) {

    Write-Host ""
    Write-Host "===== WARNINGS =====" -ForegroundColor Yellow

    foreach ($warning in $warnings) {
        Write-Host "- $warning" -ForegroundColor Yellow
    }
}

Write-Host ""
