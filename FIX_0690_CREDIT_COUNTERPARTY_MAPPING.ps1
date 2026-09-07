$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Vault = Join-Path $Repo "vault"
$Archive = Join-Path $Repo "archive"

$OutDir = Join-Path $Vault "06_Exposures\02_Credit_Counterparty"
$OutFile = Join-Path $OutDir "00_Credit_Counterparty_Map.md"

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $Archive ("credit-counterparty-0690-" + $Stamp)

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

if (Test-Path $OutFile) {
    Copy-Item $OutFile (Join-Path $BackupDir "00_Credit_Counterparty_Map.md") -Force
}

$Rows = @(
    [pscustomobject]@{
        Counterparty="Matarazzo"
        FundA="PCIP11"
        FundB="VGIP11"
        Relation="Same CRI instruments"
        Instrument="Matarazzo 451S / 22C0509668; Matarazzo 545S / 23J2162618"
        AValue="PCIP11: 92.7m combined"
        BValue="VGIP11: 91.0m in 451S; 52.0m in 545S"
        Evidence="HIGH"
        Source="PCIP11 Jul-2026; VGIP11 Jul-2026"
        Note="Direct instrument overlap confirmed."
    }
    [pscustomobject]@{
        Counterparty="Localfrio"
        FundA="PCIP11"
        FundB="VGIP11"
        Relation="Same CRI instrument"
        Instrument="CRI Localfrio / 19K0981679"
        AValue="PCIP11: 5.4m / 0.3% PL"
        BValue="VGIP11: 1.85m / 0.17% PL"
        Evidence="HIGH"
        Source="PCIP11 Jul-2026; VGIP11 Jul-2026"
        Note="Same code identified."
    }
    [pscustomobject]@{
        Counterparty="GPA / RBVA"
        FundA="PCIP11"
        FundB="HGCR11"
        Relation="Same CRI instrument"
        Instrument="GPA RBVA / 20L0687133"
        AValue="PCIP11: 2.9m / 0.2% PL"
        BValue="HGCR11: 9.8m / 0.7% PL"
        Evidence="HIGH"
        Source="PCIP11 Jul-2026; HGCR11 Jun-2026"
        Note="Same operation code."
    }
    [pscustomobject]@{
        Counterparty="GPA / RBVA"
        FundA="PCIP11"
        FundB="AFHI11"
        Relation="Same CRI instrument"
        Instrument="RBVA GPA / 20L0687133"
        AValue="PCIP11: 2.9m / 0.2% PL"
        BValue="AFHI11: 5.0m allocated position"
        Evidence="HIGH"
        Source="PCIP11 Jul-2026; AFHI11 Jun-2026"
        Note="Same operation code."
    }
    [pscustomobject]@{
        Counterparty="Rede D'Or"
        FundA="PCIP11"
        FundB="AFHI11"
        Relation="Same CRI instrument"
        Instrument="Rede D'Or / 19H0235501"
        AValue="PCIP11: 6.6m / 0.4% PL"
        BValue="AFHI11: 1.01m / 0.20% PL"
        Evidence="HIGH"
        Source="PCIP11 Jul-2026; AFHI11 Jun-2026"
        Note="Same operation code."
    }
    [pscustomobject]@{
        Counterparty="MRV"
        FundA="PCIP11"
        FundB="BTCI11"
        Relation="Same economic counterparty; different instruments"
        Instrument="PCIP11 26C4863993; BTCI11 25F1669254"
        AValue="PCIP11: 43.4m / 2.8% PL"
        BValue="BTCI11: 44.5m MTM / 4.4% PL"
        Evidence="MEDIUM-HIGH"
        Source="PCIP11 Jul-2026; BTCI11 Jul-2026"
        Note="Named MRV Flex operation in both, but codes differ."
    }
    [pscustomobject]@{
        Counterparty="Assai"
        FundA="PCIP11"
        FundB="AFHI11"
        Relation="Same economic counterparty; different operations"
        Instrument="Multiple retail CRIs"
        AValue="PCIP11: multiple Assai-linked positions"
        BValue="AFHI11: Assai GIC 4.36m plus RBVA GPA exposure"
        Evidence="MEDIUM"
        Source="PCIP11 Jul-2026; AFHI11 Jun-2026"
        Note="Economic overlap only."
    }
    [pscustomobject]@{
        Counterparty="Grupo Mateus"
        FundA="PCIP11"
        FundB="AFHI11"
        Relation="Same economic counterparty; different operations"
        Instrument="Mateus-linked CRIs"
        AValue="PCIP11: multiple Mateus-linked positions"
        BValue="AFHI11: TRX Mateus 2.84m plus Mateus exposure"
        Evidence="MEDIUM"
        Source="PCIP11 Jul-2026; AFHI11 Jun-2026"
        Note="Economic overlap only."
    }
)

$Direct = @($Rows | Where-Object { $_.Evidence -eq "HIGH" })
$Economic = @($Rows | Where-Object { $_.Evidence -ne "HIGH" })

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("---")
$lines.Add("module: credit_counterparty_mapping")
$lines.Add("version: 0.1")
$lines.Add("status: active")
$lines.Add("as_of: 2026-07-31")
$lines.Add("generated_at: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$lines.Add("---")
$lines.Add("")
$lines.Add("# 0690 - Credit Counterparty Mapping")
$lines.Add("")
$lines.Add("## Purpose")
$lines.Add("")
$lines.Add("Map direct and economic credit overlaps between PCIP11 and priority credit funds.")
$lines.Add("")
$lines.Add("## Scope")
$lines.Add("")
$lines.Add("- PCIP11")
$lines.Add("- VGIP11")
$lines.Add("- AFHI11")
$lines.Add("- HGCR11")
$lines.Add("- BTCI11")
$lines.Add("- MANA11")
$lines.Add("")
$lines.Add("MANA11 remains GAP because a sufficiently detailed July-2026 credit composition source was not located in the current library search.")
$lines.Add("No overlap is asserted for MANA11.")
$lines.Add("")
$lines.Add("## Direct credit overlaps")
$lines.Add("")

foreach ($r in $Direct) {
    $lines.Add("### " + $r.Counterparty)
    $lines.Add("")
    $lines.Add("- Funds: " + $r.FundA + " x " + $r.FundB)
    $lines.Add("- Relation: " + $r.Relation)
    $lines.Add("- Instrument: " + $r.Instrument)
    $lines.Add("- " + $r.AValue)
    $lines.Add("- " + $r.BValue)
    $lines.Add("- Evidence: " + $r.Evidence)
    $lines.Add("- Source: " + $r.Source)
    $lines.Add("- Note: " + $r.Note)
    $lines.Add("")
}

$lines.Add("## Economic counterparty overlaps")
$lines.Add("")

foreach ($r in $Economic) {
    $lines.Add("### " + $r.Counterparty)
    $lines.Add("")
    $lines.Add("- Funds: " + $r.FundA + " x " + $r.FundB)
    $lines.Add("- Relation: " + $r.Relation)
    $lines.Add("- Instrument: " + $r.Instrument)
    $lines.Add("- " + $r.AValue)
    $lines.Add("- " + $r.BValue)
    $lines.Add("- Evidence: " + $r.Evidence)
    $lines.Add("- Source: " + $r.Source)
    $lines.Add("- Note: " + $r.Note)
    $lines.Add("")
}

$lines.Add("## Rules")
$lines.Add("")
$lines.Add("1. Same code or ISIN = direct instrument overlap.")
$lines.Add("2. Same named obligor with different codes = economic counterparty overlap.")
$lines.Add("3. Same sector or tenant without identified obligor = adjacency only.")
$lines.Add("4. Missing source = GAP; absence is not treated as zero exposure.")
$lines.Add("")
$lines.Add("## Summary")
$lines.Add("")
$lines.Add("- Direct overlaps identified: " + $Direct.Count)
$lines.Add("- Economic counterparty overlaps identified: " + $Economic.Count)
$lines.Add("- MANA11: GAP")
$lines.Add("- Priority direct overlaps: Matarazzo, Localfrio, GPA/RBVA and Rede D'Or.")
$lines.Add("")
$lines.Add("## Status")
$lines.Add("")
$lines.Add("0690 COMPLETED - initial evidence layer")
$lines.Add("")

[System.IO.File]::WriteAllLines($OutFile, $lines, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "============================================================"
Write-Host "0690 - CREDIT COUNTERPARTY MAPPING"
Write-Host "============================================================"
Write-Host ""
Write-Host ("Direct overlaps        : " + $Direct.Count)
Write-Host ("Economic overlaps      : " + $Economic.Count)
Write-Host "MANA11                 : GAP"
Write-Host ("Output file            : " + $OutFile)
Write-Host ("Backup                 : " + $BackupDir)
Write-Host ""
Write-Host "DIRECT OVERLAPS"
Write-Host "------------------------------------------------------------"

foreach ($r in $Direct) {
    Write-Host ($r.FundA + " x " + $r.FundB + " -> " + $r.Counterparty + " -> " + $r.Instrument)
}

Write-Host ""
Write-Host "ECONOMIC COUNTERPARTY OVERLAPS"
Write-Host "------------------------------------------------------------"

foreach ($r in $Economic) {
    Write-Host ($r.FundA + " x " + $r.FundB + " -> " + $r.Counterparty)
}

Write-Host ""
Write-Host "============================================================"
Write-Host "STATUS: 0690 COMPLETED"
Write-Host "============================================================"
