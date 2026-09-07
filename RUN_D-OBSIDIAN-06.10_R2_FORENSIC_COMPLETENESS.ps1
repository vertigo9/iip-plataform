# ==============================================================================
# D-OBSIDIAN-06.10 R2 — FORENSIC COMPLETENESS & CANONICAL RECOVERY
# ==============================================================================
# READ-ONLY / NON-DESTRUCTIVE
#
# R2 corrige a limitação do 06.10 R1:
#   - não presume que DuplicateGroups tenha uma coluna "Status";
#   - inspeciona dinamicamente os headers;
#   - reconstrói grupos diretamente da matriz de canonicalização;
#   - valida população esperada;
#   - impede PASS quando uma população esperada não foi processada.
#
# NÃO executa:
#   Remove-Item / Move-Item / Rename-Item
#   git add / commit / restore / reset / clean
# ==============================================================================

$ErrorActionPreference = "Stop"

$Repo = (Get-Location).Path
$SourceDir = Join-Path $Repo "reports\D-OBSIDIAN-06.9-R1"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Repo "reports\D-OBSIDIAN-06.10-R2"

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host ""
Write-Host "================================================================================"
Write-Host "D-OBSIDIAN-06.10 R2 — FORENSIC COMPLETENESS & CANONICAL RECOVERY"
Write-Host "================================================================================"
Write-Host "Repository : $Repo"
Write-Host "Source     : $SourceDir"
Write-Host "Output     : $OutDir"
Write-Host "Timestamp  : $Timestamp"
Write-Host ""
Write-Host "READ-ONLY / NON-DESTRUCTIVE"
Write-Host "================================================================================"
Write-Host ""

# ------------------------------------------------------------------------------
# 01. FIND LATEST 06.9 FILES
# ------------------------------------------------------------------------------

function Get-LatestFile {
    param(
        [string]$Pattern
    )

    $Result = Get-ChildItem -LiteralPath $SourceDir -File `
        -Filter $Pattern |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $Result) {
        throw "Arquivo não encontrado: $Pattern"
    }

    return $Result
}

$DecisionFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv"
$CanonicalFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_CANONICALIZATION_*.csv"
$DuplicateFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_DUPLICATE_GROUPS_*.csv"
$CandidateFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_D_CANDIDATES_*.csv"
$CriticalFile = Get-LatestFile "D-OBSIDIAN-06.9_R1_CRITICAL_REFERENCES_*.csv"

Write-Host "SOURCE FILES"
Write-Host "  $($DecisionFile.Name)"
Write-Host "  $($CanonicalFile.Name)"
Write-Host "  $($DuplicateFile.Name)"
Write-Host "  $($CandidateFile.Name)"
Write-Host "  $($CriticalFile.Name)"
Write-Host ""

# ------------------------------------------------------------------------------
# 02. LOAD
# ------------------------------------------------------------------------------

$DecisionRows = @(Import-Csv -LiteralPath $DecisionFile.FullName)
$CanonicalRows = @(Import-Csv -LiteralPath $CanonicalFile.FullName)
$DuplicateRows = @(Import-Csv -LiteralPath $DuplicateFile.FullName)
$CandidateRows = @(Import-Csv -LiteralPath $CandidateFile.FullName)
$CriticalRows = @(Import-Csv -LiteralPath $CriticalFile.FullName)

Write-Host "INPUT COUNTS"
Write-Host "  Decision       : $($DecisionRows.Count)"
Write-Host "  Canonical      : $($CanonicalRows.Count)"
Write-Host "  Duplicate      : $($DuplicateRows.Count)"
Write-Host "  Candidates     : $($CandidateRows.Count)"
Write-Host "  Critical Refs  : $($CriticalRows.Count)"
Write-Host ""

# ------------------------------------------------------------------------------
# 03. HEADER DIAGNOSTIC
# ------------------------------------------------------------------------------

function Show-Headers {
    param(
        [string]$Name,
        [object[]]$Rows
    )

    if ($Rows.Count -eq 0) {
        Write-Host "$Name : EMPTY"
        return
    }

    Write-Host "$Name HEADERS:"
    ($Rows[0].PSObject.Properties.Name |
        ForEach-Object { "  $_" }) |
        Write-Host
}

Show-Headers "DECISION" $DecisionRows
Show-Headers "CANONICAL" $CanonicalRows
Show-Headers "DUPLICATE" $DuplicateRows
Show-Headers "CANDIDATE" $CandidateRows
Show-Headers "CRITICAL" $CriticalRows

Write-Host ""

# ------------------------------------------------------------------------------
# 04. NORMALIZATION
# ------------------------------------------------------------------------------

function Normalize-Path {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }

    $P = $Path.Trim() -replace "\\", "/"
    $RepoNorm = $Repo -replace "\\", "/"

    if ($P.StartsWith($RepoNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
        $P = $P.Substring($RepoNorm.Length).TrimStart("/")
    }

    return $P.TrimStart("./")
}

function Get-PropertyValue {
    param(
        [object]$Row,
        [string[]]$Names
    )

    foreach ($Name in $Names) {
        $Prop = $Row.PSObject.Properties |
            Where-Object {
                $_.Name.Equals($Name, [System.StringComparison]::OrdinalIgnoreCase)
            } |
            Select-Object -First 1

        if ($Prop) {
            $Value = $Prop.Value

            if (-not [string]::IsNullOrWhiteSpace([string]$Value)) {
                return [string]$Value
            }
        }
    }

    return ""
}

function Get-RowPath {
    param(
        [object]$Row
    )

    return Normalize-Path (
        Get-PropertyValue $Row @(
            "Path",
            "FilePath",
            "RelativePath",
            "RepoPath",
            "FullName"
        )
    )
}

function Get-RowHash {
    param(
        [object]$Row
    )

    return (
        Get-PropertyValue $Row @(
            "Hash",
            "SHA256",
            "Sha256",
            "FileHash"
        )
    ).ToUpperInvariant()
}

# ------------------------------------------------------------------------------
# 05. PROTECTION
# ------------------------------------------------------------------------------

$ProtectedPrefixes = @(
    "data/",
    "vault/",
    "archive/",
    "tests/intelligence/",
    "tests/integration/"
)

$ProtectedExact = @(
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py"
)

function Get-Protection {
    param(
        [string]$Path
    )

    $P = Normalize-Path $Path

    foreach ($Exact in $ProtectedExact) {
        if ($P.Equals($Exact, [System.StringComparison]::OrdinalIgnoreCase)) {
            return "PROTECTED-CRITICAL"
        }
    }

    foreach ($Prefix in $ProtectedPrefixes) {
        if ($P.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return "PROTECTED"
        }
    }

    return "NORMAL"
}

function Resolve-File {
    param(
        [string]$Path
    )

    $P = Normalize-Path $Path

    if ([string]::IsNullOrWhiteSpace($P)) {
        return $null
    }

    $Full = Join-Path $Repo ($P -replace "/", "\")

    if (Test-Path -LiteralPath $Full -PathType Leaf) {
        return Get-Item -LiteralPath $Full
    }

    return $null
}

# ------------------------------------------------------------------------------
# 06. DETERMINE EXPECTED POPULATIONS
# ------------------------------------------------------------------------------

$ExpectedRemove = @(
    $DecisionRows |
        Where-Object {
            (Get-PropertyValue $_ @("Decision")).Equals(
                "REMOVE-CANDIDATE",
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }
)

$ExpectedReview = @(
    $DecisionRows |
        Where-Object {
            (Get-PropertyValue $_ @("Decision")).Equals(
                "REVIEW-DUPLICATE",
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }
)

# Canonicalization source is authoritative for reconstruction.
$CanonicalHashes = @(
    $CanonicalRows |
        ForEach-Object {
            Get-RowHash $_
        } |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace($_)
        } |
        Sort-Object -Unique
)

$CanonicalGroupRows = @()

foreach ($Hash in $CanonicalHashes) {

    $Rows = @(
        $CanonicalRows |
            Where-Object {
                (Get-RowHash $_) -eq $Hash
            }
    )

    if ($Rows.Count -gt 1) {
        $CanonicalGroupRows += [PSCustomObject]@{
            Hash      = $Hash
            RowCount  = $Rows.Count
            Rows      = $Rows
        }
    }
}

Write-Host "EXPECTED POPULATIONS"
Write-Host "  REMOVE-CANDIDATE : $($ExpectedRemove.Count)"
Write-Host "  REVIEW-DUPLICATE : $($ExpectedReview.Count)"
Write-Host "  UNIQUE HASHES    : $($CanonicalHashes.Count)"
Write-Host "  CANONICAL GROUPS : $($CanonicalGroupRows.Count)"
Write-Host ""

# ------------------------------------------------------------------------------
# 07. RECONSTRUCT CANONICAL GROUPS
# ------------------------------------------------------------------------------

$CanonicalForensics = [System.Collections.Generic.List[object]]::new()

foreach ($Group in $CanonicalGroupRows) {

    $Rows = @($Group.Rows)

    $Paths = @(
        $Rows |
            ForEach-Object {
                Get-RowPath $_
            } |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace($_)
            } |
            Sort-Object -Unique
    )

    $CanonicalPath = ""

    # Prefer explicit canonical indicators if available.
    foreach ($R in $Rows) {

        $Status = Get-PropertyValue $R @(
            "CanonicalStatus",
            "Status",
            "Role",
            "Classification"
        )

        $CandidateCanonical = Get-PropertyValue $R @(
            "CanonicalPath",
            "Canonical",
            "CanonicalFile"
        )

        if (
            $Status -match "CANONICAL" -and
            -not [string]::IsNullOrWhiteSpace($CandidateCanonical)
        ) {
            $CanonicalPath = Normalize-Path $CandidateCanonical
            break
        }
    }

    # If no explicit canonical path exists, inspect row path + status.
    if ([string]::IsNullOrWhiteSpace($CanonicalPath)) {

        foreach ($R in $Rows) {

            $Status = Get-PropertyValue $R @(
                "CanonicalStatus",
                "Status",
                "Role",
                "Classification"
            )

            if ($Status -match "CANONICAL") {
                $CanonicalPath = Get-RowPath $R
                break
            }
        }
    }

    # Last-resort deterministic selection:
    # prefer non-archive, non-backup, non-copy path.
    if ([string]::IsNullOrWhiteSpace($CanonicalPath)) {

        $Preferred = @(
            $Paths |
                Where-Object {
                    $_ -notmatch "(^|/)(archive|backup|backups)(/|$)" -and
                    $_ -notmatch "(\(|copy|backup|bak|old|legacy)"
                } |
                Select-Object -First 1
        )

        if ($Preferred.Count -gt 0) {
            $CanonicalPath = $Preferred[0]
        }
    }

    foreach ($Path in $Paths) {

        if ($Path -eq $CanonicalPath) {
            continue
        }

        $CanonicalItem = Resolve-File $CanonicalPath
        $DuplicateItem = Resolve-File $Path

        $Protection = if (
            (Get-Protection $CanonicalPath) -ne "NORMAL" -or
            (Get-Protection $Path) -ne "NORMAL"
        ) {
            "PROTECTED"
        }
        else {
            "NORMAL"
        }

        $Action = "REVIEW-CANONICAL-DUPLICATE"

        if ($Protection -ne "NORMAL") {
            $Action = "DO-NOT-TOUCH"
        }
        elseif (-not $CanonicalItem) {
            $Action = "REVIEW-MISSING-CANONICAL"
        }
        elseif (-not $DuplicateItem) {
            $Action = "REVIEW-MISSING-DUPLICATE"
        }

        $CanonicalForensics.Add([PSCustomObject]@{
            Hash              = $Group.Hash
            GroupSize         = $Paths.Count
            CanonicalPath     = $CanonicalPath
            DuplicatePath     = $Path
            CanonicalExists   = ($null -ne $CanonicalItem)
            DuplicateExists   = ($null -ne $DuplicateItem)
            CanonicalProtect  = Get-Protection $CanonicalPath
            DuplicateProtect  = Get-Protection $Path
            ProvisionalAction = $Action
        })
    }
}

# ------------------------------------------------------------------------------
# 08. REMOVE FORENSICS
# ------------------------------------------------------------------------------

$RemoveForensics = [System.Collections.Generic.List[object]]::new()

foreach ($Row in $ExpectedRemove) {

    $Path = Get-RowPath $Row
    $Item = Resolve-File $Path
    $Protection = Get-Protection $Path

    $Hash = ""
    $Size = ""

    if ($Item) {
        $Size = $Item.Length

        try {
            $Hash = (Get-FileHash `
                -LiteralPath $Item.FullName `
                -Algorithm SHA256).Hash
        }
        catch {
            $Hash = "HASH_ERROR"
        }
    }

    $Action = "NEEDS-APPROVAL"

    if ($Protection -ne "NORMAL") {
        $Action = "DO-NOT-TOUCH"
    }
    elseif ($null -eq $Item) {
        $Action = "ALREADY-ABSENT"
    }

    $RemoveForensics.Add([PSCustomObject]@{
        Path              = $Path
        Class             = Get-PropertyValue $Row @("Class")
        Type              = Get-PropertyValue $Row @("Type")
        Policy            = Get-PropertyValue $Row @("Policy")
        Decision          = Get-PropertyValue $Row @("Decision")
        Protection        = $Protection
        Exists             = ($null -ne $Item)
        SizeBytes          = $Size
        SHA256             = $Hash
        ProvisionalAction = $Action
        Reason             = Get-PropertyValue $Row @("Reason")
    })
}

# ------------------------------------------------------------------------------
# 09. REVIEW FORENSICS
# ------------------------------------------------------------------------------

$ReviewForensics = [System.Collections.Generic.List[object]]::new()

foreach ($Row in $ExpectedReview) {

    $Path = Get-RowPath $Row
    $Protection = Get-Protection $Path

    $Action = "REVIEW"

    $Type = Get-PropertyValue $Row @("Type")

    if ($Protection -ne "NORMAL") {
        $Action = "DO-NOT-TOUCH"
    }
    elseif ($Type -match "BRIDGE|PATCH") {
        $Action = "TRANSITION-REVIEW"
    }

    $ReviewForensics.Add([PSCustomObject]@{
        Path              = $Path
        Class             = Get-PropertyValue $Row @("Class")
        Type              = $Type
        Policy            = Get-PropertyValue $Row @("Policy")
        Decision          = Get-PropertyValue $Row @("Decision")
        Protection        = $Protection
        Exists             = ($null -ne (Resolve-File $Path))
        ProvisionalAction = $Action
    })
}

# ------------------------------------------------------------------------------
# 10. INVARIANTS
# ------------------------------------------------------------------------------

$Invariants = [System.Collections.Generic.List[object]]::new()

function Add-Invariant {
    param(
        [string]$Name,
        [bool]$Pass,
        [string]$Detail
    )

    $Invariants.Add([PSCustomObject]@{
        Invariant = $Name
        Status    = if ($Pass) { "PASS" } else { "FAIL" }
        Detail    = $Detail
    })
}

# Exact expected populations.
Add-Invariant `
    "REMOVE_POPULATION_COMPLETE" `
    ($RemoveForensics.Count -eq $ExpectedRemove.Count) `
    "Expected=$($ExpectedRemove.Count); Processed=$($RemoveForensics.Count)"

Add-Invariant `
    "REVIEW_POPULATION_COMPLETE" `
    ($ReviewForensics.Count -eq $ExpectedReview.Count) `
    "Expected=$($ExpectedReview.Count); Processed=$($ReviewForensics.Count)"

Add-Invariant `
    "CANONICAL_GROUPS_DETECTED" `
    ($CanonicalGroupRows.Count -gt 0) `
    "Canonical groups reconstructed=$($CanonicalGroupRows.Count)"

# The known 06.9 baseline was 63 HAS-CANONICAL groups.
$KnownCanonicalGroups = 63

Add-Invariant `
    "KNOWN_CANONICAL_BASELINE" `
    ($CanonicalGroupRows.Count -eq $KnownCanonicalGroups) `
    "Expected=$KnownCanonicalGroups; Detected=$($CanonicalGroupRows.Count)"

# No protected item can become actionable.
$ProtectedActions = @(
    $CanonicalForensics |
        Where-Object {
            $_.CanonicalProtect -ne "NORMAL" -or
            $_.DuplicateProtect -ne "NORMAL"
        } |
        Where-Object {
            $_.ProvisionalAction -ne "DO-NOT-TOUCH"
        }
)

Add-Invariant `
    "PROTECTED_CANONICAL_GUARD" `
    ($ProtectedActions.Count -eq 0) `
    "Protected canonical rows with actionable state=$($ProtectedActions.Count)"

$ProtectedRemove = @(
    $RemoveForensics |
        Where-Object {
            $_.Protection -ne "NORMAL" -and
            $_.ProvisionalAction -ne "DO-NOT-TOUCH"
        }
)

Add-Invariant `
    "PROTECTED_REMOVE_GUARD" `
    ($ProtectedRemove.Count -eq 0) `
    "Protected remove candidates with actionable state=$($ProtectedRemove.Count)"

# Critical components.
foreach ($Critical in $ProtectedExact) {

    $Exists = $null -ne (Resolve-File $Critical)

    Add-Invariant `
        "CRITICAL_EXISTS::$Critical" `
        $Exists `
        "Exists=$Exists"
}

# Protected trees.
foreach ($Prefix in $ProtectedPrefixes) {

    $Directory = Join-Path `
        $Repo `
        ($Prefix.TrimEnd("/") -replace "/", "\")

    $Exists = Test-Path -LiteralPath $Directory -PathType Container

    Add-Invariant `
        "PROTECTED_TREE::$Prefix" `
        $Exists `
        "Exists=$Exists"
}

# 06.9 inputs must exist.
foreach ($Source in @(
    $DecisionFile,
    $CanonicalFile,
    $DuplicateFile,
    $CandidateFile,
    $CriticalFile
)) {

    Add-Invariant `
        "SOURCE_EXISTS::$($Source.Name)" `
        (Test-Path -LiteralPath $Source.FullName -PathType Leaf) `
        "Source exists."
}

# ------------------------------------------------------------------------------
# 11. GATE
# ------------------------------------------------------------------------------

$Gate = $true

foreach ($I in $Invariants) {

    if ($I.Status -eq "FAIL") {
        $Gate = $false
    }
}

# ------------------------------------------------------------------------------
# 12. OUTPUTS
# ------------------------------------------------------------------------------

$CanonicalOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R2_CANONICAL_FORENSICS_$Timestamp.csv"

$RemoveOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R2_REMOVE_FORENSICS_$Timestamp.csv"

$ReviewOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R2_REVIEW_FORENSICS_$Timestamp.csv"

$InvariantOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R2_INVARIANTS_$Timestamp.csv"

$SummaryOut = Join-Path `
    $OutDir `
    "D-OBSIDIAN-06.10_R2_SUMMARY_$Timestamp.txt"

$CanonicalForensics |
    Export-Csv -LiteralPath $CanonicalOut -NoTypeInformation -Encoding UTF8

$RemoveForensics |
    Export-Csv -LiteralPath $RemoveOut -NoTypeInformation -Encoding UTF8

$ReviewForensics |
    Export-Csv -LiteralPath $ReviewOut -NoTypeInformation -Encoding UTF8

$Invariants |
    Export-Csv -LiteralPath $InvariantOut -NoTypeInformation -Encoding UTF8

$Summary = [System.Collections.Generic.List[string]]::new()

$Summary.Add("D-OBSIDIAN-06.10 R2 — FORENSIC COMPLETENESS & CANONICAL RECOVERY")
$Summary.Add("Repository: $Repo")
$Summary.Add("Timestamp: $Timestamp")
$Summary.Add("")
$Summary.Add("INPUT:")
$Summary.Add("  Decision rows       : $($DecisionRows.Count)")
$Summary.Add("  Canonical rows      : $($CanonicalRows.Count)")
$Summary.Add("  Duplicate rows      : $($DuplicateRows.Count)")
$Summary.Add("  Candidate rows      : $($CandidateRows.Count)")
$Summary.Add("  Critical refs       : $($CriticalRows.Count)")
$Summary.Add("")
$Summary.Add("POPULATIONS:")
$Summary.Add("  REMOVE expected     : $($ExpectedRemove.Count)")
$Summary.Add("  REMOVE processed    : $($RemoveForensics.Count)")
$Summary.Add("  REVIEW expected     : $($ExpectedReview.Count)")
$Summary.Add("  REVIEW processed    : $($ReviewForensics.Count)")
$Summary.Add("  CANONICAL expected  : $KnownCanonicalGroups")
$Summary.Add("  CANONICAL detected  : $($CanonicalGroupRows.Count)")
$Summary.Add("")
$Summary.Add("CANONICAL ACTIONS:")

foreach ($G in ($CanonicalForensics | Group-Object ProvisionalAction)) {
    $Summary.Add("  $($G.Name): $($G.Count)")
}

$Summary.Add("")
$Summary.Add("REMOVE ACTIONS:")

foreach ($G in ($RemoveForensics | Group-Object ProvisionalAction)) {
    $Summary.Add("  $($G.Name): $($G.Count)")
}

$Summary.Add("")
$Summary.Add("REVIEW ACTIONS:")

foreach ($G in ($ReviewForensics | Group-Object ProvisionalAction)) {
    $Summary.Add("  $($G.Name): $($G.Count)")
}

$Summary.Add("")
$Summary.Add("INVARIANTS:")

foreach ($I in $Invariants) {
    $Summary.Add("  [$($I.Status)] $($I.Invariant) — $($I.Detail)")
}

$Summary.Add("")
$Summary.Add("SAFETY:")
$Summary.Add("  No files removed.")
$Summary.Add("  No files moved.")
$Summary.Add("  No files renamed.")
$Summary.Add("  No contents modified.")
$Summary.Add("  No git add.")
$Summary.Add("  No git commit.")
$Summary.Add("  No git restore.")
$Summary.Add("  No git reset.")
$Summary.Add("  No git clean.")
$Summary.Add("")

if ($Gate) {
    $Summary.Add("FORENSIC COMPLETENESS GATE: PASS")
}
else {
    $Summary.Add("FORENSIC COMPLETENESS GATE: FAIL")
}

$Summary |
    Set-Content -LiteralPath $SummaryOut -Encoding UTF8

# ------------------------------------------------------------------------------
# 13. CONSOLE
# ------------------------------------------------------------------------------

Write-Host ""
Write-Host "================================================================================"
Write-Host "D-OBSIDIAN-06.10 R2 — RESULTADO"
Write-Host "================================================================================"
Write-Host ""

Write-Host "REMOVE-CANDIDATE"
Write-Host "  Expected : $($ExpectedRemove.Count)"
Write-Host "  Processed: $($RemoveForensics.Count)"

Write-Host ""
Write-Host "REVIEW-DUPLICATE"
Write-Host "  Expected : $($ExpectedReview.Count)"
Write-Host "  Processed: $($ReviewForensics.Count)"

Write-Host ""
Write-Host "HAS-CANONICAL"
Write-Host "  Expected : $KnownCanonicalGroups"
Write-Host "  Detected : $($CanonicalGroupRows.Count)"

Write-Host ""
Write-Host "INVARIANTS"

foreach ($I in $Invariants) {

    if ($I.Status -eq "PASS") {
        Write-Host "[PASS] $($I.Invariant)" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $($I.Invariant)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "OUTPUTS"
Write-Host "  $CanonicalOut"
Write-Host "  $RemoveOut"
Write-Host "  $ReviewOut"
Write-Host "  $InvariantOut"
Write-Host "  $SummaryOut"

Write-Host ""

if ($Gate) {
    Write-Host "================================================================================"
    Write-Host "FORENSIC COMPLETENESS GATE: PASS" -ForegroundColor Green
    Write-Host "================================================================================"
}
else {
    Write-Host "================================================================================"
    Write-Host "FORENSIC COMPLETENESS GATE: FAIL" -ForegroundColor Red
    Write-Host "================================================================================"
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.10 R2 concluído em modo READ-ONLY."
